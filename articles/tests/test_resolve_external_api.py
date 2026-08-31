"""Tests for POST /articles/resolve-external/.

The endpoint exists so a user reading a PubMed paper in the feed can post it to a
community even when someone else already ingested that paper. `create_article` cannot
serve that case -- it answers with a bare 400 carrying no slug -- so the second person to
post a popular paper would otherwise be stuck. These tests pin that behaviour down.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from articles.api import router
from articles.models import Article, ArticlePDF
from communities.articles_api import router as community_articles_router
from communities.models import Community, CommunityArticle

User = get_user_model()

PMID = "42460417"
PUBMED_LINK = f"https://pubmed.ncbi.nlm.nih.gov/{PMID}/"


def payload_for(**overrides):
    payload = {
        "source": "pubmed",
        "external_id": PMID,
        "title": "CRISPR-mediated targeting of the LMNA c.745C>T mutation",
        "abstract": "LMNA-associated congenital muscular dystrophy is a rare disorder.",
        "authors": [{"value": "Deborah Gomez-Dominguez", "label": "Deborah Gomez-Dominguez"}],
        "article_link": PUBMED_LINK,
    }
    payload.update(overrides)
    return payload


class ResolveExternalArticleTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="reader", email="reader@example.com", password="password123"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="password123"
        )

    def auth_headers(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"Authorization": f"Bearer {token}"}

    def post(self, payload, user=None):
        return self.client.post(
            "/articles/resolve-external/", json=payload, headers=self.auth_headers(user)
        )

    def test_creates_article_when_not_yet_ingested(self):
        response = self.post(payload_for())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["created"])
        self.assertTrue(body["slug"])

        article = Article.objects.get(id=body["article_id"])
        self.assertEqual(article.article_link, PUBMED_LINK)
        self.assertEqual(article.submitter, self.user)

    def test_returns_existing_slug_instead_of_erroring(self):
        """The case create_article cannot handle: a second user posting the same paper."""
        first = self.post(payload_for()).json()

        second = self.post(payload_for(), user=self.other_user)

        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertFalse(body["created"])
        self.assertEqual(body["slug"], first["slug"])
        self.assertEqual(body["article_id"], first["article_id"])
        # Crucially, no duplicate row -- both users act on one shared article.
        self.assertEqual(Article.objects.filter(article_link=PUBMED_LINK).count(), 1)

    def test_identical_title_and_abstract_do_not_block_a_different_paper(self):
        """create_article rejects a matching (title, abstract) pair; resolve must not."""
        self.post(payload_for())

        other_pmid_link = "https://pubmed.ncbi.nlm.nih.gov/42205224/"
        response = self.post(payload_for(external_id="42205224", article_link=other_pmid_link))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])
        self.assertEqual(Article.objects.count(), 2)

    def test_stores_pdf_link_when_supplied(self):
        response = self.post(
            payload_for(pdf_link="https://pmc.ncbi.nlm.nih.gov/articles/PMC13370164/")
        )

        article_id = response.json()["article_id"]
        pdf = ArticlePDF.objects.get(article_id=article_id)
        self.assertEqual(pdf.external_url, "https://pmc.ncbi.nlm.nih.gov/articles/PMC13370164/")

    def test_rejects_blank_article_link(self):
        response = self.post(payload_for(article_link="   "))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Article.objects.count(), 0)

    def test_requires_authentication(self):
        response = self.client.post("/articles/resolve-external/", json=payload_for())

        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(Article.objects.count(), 0)


class PostFeedArticleToCommunityTest(TestCase):
    """End-to-end cover for what the feed's "Post to community" button does.

    The UI makes two calls -- resolve the PubMed record to a slug, then submit that slug to
    the chosen community. These tests exercise that exact pair, including the outcomes the
    UI has to render as ordinary messages rather than failures.
    """

    def setUp(self):
        self.articles_client = TestClient(router)
        self.communities_client = TestClient(community_articles_router)
        self.user = User.objects.create_user(
            username="reader", email="reader@example.com", password="password123"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="password123"
        )
        # Every real community has a creator-admin. Without one, submit-article's
        # "notify the admins" step fails on a null user_id, so an admin-less community is
        # not a realistic fixture.
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="password123"
        )
        self.public_community = self.make_community("open-science", Community.PUBLIC)
        self.private_community = self.make_community("closed-lab", Community.PRIVATE)

    def make_community(self, name, community_type):
        community = Community.objects.create(name=name, type=community_type)
        community.admins.add(self.admin)
        return community

    def headers(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"Authorization": f"Bearer {token}"}

    def post_to_community(self, community_name, user=None, **payload_overrides):
        """The two calls the button makes, in order."""
        resolved = self.articles_client.post(
            "/articles/resolve-external/",
            json=payload_for(**payload_overrides),
            headers=self.headers(user),
        )
        self.assertEqual(resolved.status_code, 200, resolved.content)
        slug = resolved.json()["slug"]

        return self.communities_client.post(
            f"/communities/{community_name}/submit-article/{slug}",
            headers=self.headers(user),
        )

    def test_posts_a_feed_article_to_a_public_community(self):
        response = self.post_to_community("open-science")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(
            CommunityArticle.objects.filter(
                community=self.public_community, article__article_link=PUBMED_LINK
            ).exists()
        )

    def test_second_user_can_post_the_same_paper_to_a_different_community(self):
        """The scenario that fails without the resolve endpoint."""
        self.post_to_community("open-science")

        another_public = self.make_community("genetics-hub", Community.PUBLIC)
        response = self.post_to_community("genetics-hub", user=self.other_user)

        self.assertEqual(response.status_code, 200, response.content)
        article = Article.objects.get(article_link=PUBMED_LINK)
        self.assertEqual(CommunityArticle.objects.filter(article=article).count(), 2)
        self.assertTrue(
            CommunityArticle.objects.filter(community=another_public, article=article).exists()
        )

    def test_posting_twice_to_the_same_community_is_reported_cleanly(self):
        self.post_to_community("open-science")

        response = self.post_to_community("open-science")

        self.assertEqual(response.status_code, 400)
        self.assertIn("already submitted", response.json()["message"].lower())
        self.assertEqual(CommunityArticle.objects.count(), 1)

    def test_non_member_cannot_post_to_a_private_community(self):
        response = self.post_to_community("closed-lab")

        self.assertEqual(response.status_code, 400)
        self.assertIn("member", response.json()["message"].lower())
        self.assertEqual(CommunityArticle.objects.count(), 0)
