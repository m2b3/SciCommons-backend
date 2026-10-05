from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from articles import api as articles_api
from articles.models import Article
from articles.schemas import ArticleFilters
from communities.models import Community, CommunityArticle
from myapp.schemas import FilterType
from users.models import Hashtag, HashtagRelation

User = get_user_model()


class RelevantArticlesApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="submitter", email="submitter@example.com", password="pw123456")
        self.hashtag = Hashtag.objects.create(name="neuroscience")

        self.public_community = Community.objects.create(
            name="Public Community", slug="public-community", type=Community.PUBLIC
        )
        self.other_community = Community.objects.create(
            name="Other Community", slug="other-community", type=Community.PUBLIC
        )
        self.hidden_community = Community.objects.create(
            name="Hidden Community", slug="hidden-community", type=Community.HIDDEN
        )

        self.base = self.create_article("Base article")
        self.in_community = self.create_article("Related in community", community=self.public_community)
        self.in_other_community = self.create_article("Related elsewhere", community=self.other_community)
        self.in_hidden_community = self.create_article("Related but hidden", community=self.hidden_community)

    def create_article(self, title, community=None):
        article = Article.objects.create(
            title=title,
            abstract=f"{title} abstract",
            authors=["Author One"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        HashtagRelation.objects.create(
            hashtag=self.hashtag,
            content_type=ContentType.objects.get_for_model(Article),
            object_id=article.id,
        )
        if community:
            CommunityArticle.objects.create(article=article, community=community, status=CommunityArticle.PUBLISHED)
        return article

    def get_relevant(self, community_id=None):
        filters = ArticleFilters(filter_type=FilterType.RECENT, community_id=community_id)
        return articles_api.get_relevant_articles(SimpleNamespace(auth=None), self.base.id, filters)

    def test_without_community_returns_related_articles_except_hidden(self):
        status, result = self.get_relevant()

        self.assertEqual(status, 200)
        self.assertEqual(
            {article.id for article in result},
            {self.in_community.id, self.in_other_community.id},
        )

    def test_community_filter_returns_only_that_communitys_articles(self):
        status, result = self.get_relevant(community_id=self.public_community.id)

        self.assertEqual(status, 200)
        self.assertEqual([article.id for article in result], [self.in_community.id])

    def test_community_filter_still_excludes_hidden_communities(self):
        status, result = self.get_relevant(community_id=self.hidden_community.id)

        self.assertEqual(status, 200)
        self.assertEqual(result, [])
