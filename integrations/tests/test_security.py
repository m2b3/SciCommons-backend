"""Security regression tests for the integrations endpoints (PR 168 audit).

One test (or small group) per audited defect. The most important is
`test_cannot_attach_to_a_private_community_without_membership` -- `_resolve_community` took no
user at all, so any authenticated user could attach a paper to any private or hidden community
and `_community_status` published it immediately.

Also covers the community-list save feature: multiple names, per-name failure reporting, and the
"no community -> general articles" fallback.

Class-level overrides:
  * `CACHES` -> locmem, so the import idempotency cache does not touch the shared dev Redis.
  * `RATELIMIT_ENABLE=False`, since the auth endpoints are now rate limited and TestClient
    presents a constant IP, which would otherwise make these tests order-dependent.
"""

import base64
import hashlib

from django.test import TestCase, override_settings
from ninja.testing import TestClient

from articles.models import Article
from communities.models import Community, CommunityArticle, Membership
from integrations.api import router
from integrations.models import IntegrationAuthCode, IntegrationDeviceAuth
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import User

LOCMEM_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

BASE_OVERRIDES = dict(
    FRONTEND_URL="http://localhost:3000",
    DEBUG=True,
    RATELIMIT_ENABLE=False,
    CACHES=LOCMEM_CACHES,
    INTEGRATION_ALLOWED_CLIENT_IDS=["scicommons-zotero", "scicommons-clipper"],
)


def auth_header(user):
    return {"Authorization": f"Bearer {RefreshToken.for_user(user).access_token}"}


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@override_settings(**BASE_OVERRIDES)
class CommunityImportAuthorizationTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.member = User.objects.create_user(
            username="member", email="member@example.com", password="pw", is_active=True
        )
        self.outsider = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="pw", is_active=True
        )
        self.admin = User.objects.create_user(
            username="cadmin", email="cadmin@example.com", password="pw", is_active=True
        )

        self.private = self.make_community("Private Lab", Community.PRIVATE)
        self.hidden = self.make_community("Hidden Lab", Community.HIDDEN)
        self.public = self.make_community("Open Science", Community.PUBLIC)
        Membership.objects.create(user=self.member, community=self.private)
        Membership.objects.create(user=self.member, community=self.hidden)

    def make_community(self, name, community_type):
        community = Community.objects.create(name=name, type=community_type, slug=name.lower().replace(" ", "-"))
        community.admins.add(self.admin)
        return community

    def import_paper(self, user, **payload):
        body = {"title": "A Paper", "doi": "10.1234/paper"}
        body.update(payload)
        return self.client.post("/papers/import", json=body, headers=auth_header(user))

    def test_cannot_attach_to_a_private_community_without_membership(self):
        response = self.import_paper(self.outsider, community_names=["Private Lab"])

        self.assertEqual(response.status_code, 200, response.content)
        results = response.json()["communities"]
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["attached"])
        self.assertIn("member", results[0]["error"].lower())
        # Nothing may be attached, and crucially nothing published.
        self.assertFalse(CommunityArticle.objects.filter(community=self.private).exists())

    def test_cannot_attach_to_a_hidden_community_without_membership(self):
        response = self.import_paper(self.outsider, community_names=["Hidden Lab"])

        self.assertFalse(response.json()["communities"][0]["attached"])
        self.assertFalse(CommunityArticle.objects.filter(community=self.hidden).exists())

    def test_member_can_attach_to_their_private_community(self):
        response = self.import_paper(self.member, community_names=["Private Lab"])

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["communities"][0]
        self.assertTrue(result["attached"])
        self.assertEqual(result["status"], CommunityArticle.PUBLISHED)
        self.assertIn("/community/Private%20Lab/articles/a-paper", result["article_url"])
        self.assertEqual(response.json()["article_url"], result["article_url"])
        self.assertTrue(CommunityArticle.objects.filter(community=self.private).exists())
        self.assertEqual(Article.objects.get(id=response.json()["article_id"]).submission_type, "Private")

    def test_member_reuses_private_article_visible_through_requested_community(self):
        existing = Article.objects.create(
            title="Existing community paper",
            abstract="",
            authors=[],
            doi="10.1234/paper",
            submission_type="Private",
            submitter=self.admin,
        )
        CommunityArticle.objects.create(
            article=existing,
            community=self.private,
            status=CommunityArticle.PUBLISHED,
        )

        response = self.import_paper(self.member, community_names=["Private Lab"])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["found_existing"])
        self.assertEqual(response.json()["article_id"], existing.id)
        self.assertEqual(Article.objects.filter(doi="10.1234/paper").count(), 1)
        self.assertEqual(CommunityArticle.objects.filter(community=self.private).count(), 1)

    def test_public_community_is_open_and_lands_as_submitted(self):
        """Matches the existing submit_article policy: public communities accept any user."""
        response = self.import_paper(self.outsider, community_names=["Open Science"])

        result = response.json()["communities"][0]
        self.assertTrue(result["attached"])
        self.assertEqual(result["status"], CommunityArticle.SUBMITTED)

    def test_legacy_single_community_name_is_still_authorized(self):
        """The old field must not bypass the new check."""
        response = self.import_paper(self.outsider, community_name="Private Lab")

        self.assertFalse(response.json()["communities"][0]["attached"])
        self.assertFalse(CommunityArticle.objects.filter(community=self.private).exists())

    def test_legacy_community_id_is_still_authorized(self):
        response = self.import_paper(self.outsider, community_id=self.private.id)

        self.assertFalse(response.json()["communities"][0]["attached"])
        self.assertFalse(CommunityArticle.objects.filter(community=self.private).exists())


@override_settings(**BASE_OVERRIDES)
class CommunityListFeatureTest(TestCase):
    """The feature: type a comma-separated list; empty means save to articles."""

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="zoteronaut", email="z@example.com", password="pw", is_active=True
        )
        self.admin = User.objects.create_user(username="ca", email="ca@example.com", password="pw", is_active=True)
        self.one = self.make_community("Neuro")
        self.two = self.make_community("Gene Editing")

    def make_community(self, name):
        community = Community.objects.create(
            name=name, type=Community.PUBLIC, slug=name.lower().replace(" ", "-")
        )
        community.admins.add(self.admin)
        return community

    def import_paper(self, **payload):
        body = {"title": "Multi-community paper", "doi": "10.1234/multi"}
        body.update(payload)
        return self.client.post("/papers/import", json=body, headers=auth_header(self.user))

    def test_attaches_to_every_named_community(self):
        response = self.import_paper(community_names=["Neuro", "Gene Editing"])

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        results = body["communities"]
        self.assertEqual([r["name"] for r in results], ["Neuro", "Gene Editing"])
        self.assertTrue(all(r["attached"] for r in results))
        self.assertIn("/community/Neuro/articles/multi-community-paper", results[0]["article_url"])
        self.assertIn("/community/Gene%20Editing/articles/multi-community-paper", results[1]["article_url"])
        self.assertEqual(body["article_url"], results[0]["article_url"])
        self.assertEqual(CommunityArticle.objects.count(), 2)
        # One article, two community rows.
        self.assertEqual(Article.objects.count(), 1)

    def test_no_community_saves_to_articles_only(self):
        response = self.import_paper()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["communities"], [])
        self.assertIsNone(response.json()["community_article_id"])
        self.assertIn("/article/", response.json()["article_url"])
        self.assertNotIn("/community/", response.json()["article_url"])
        self.assertEqual(Article.objects.count(), 1)
        self.assertEqual(Article.objects.get().submission_type, "Public")
        self.assertEqual(CommunityArticle.objects.count(), 0)

    def test_client_cannot_make_no_community_import_private(self):
        response = self.import_paper(submission_type="Private")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["communities"], [])
        self.assertEqual(Article.objects.get().submission_type, "Public")

    def test_unknown_name_is_reported_without_losing_the_valid_ones(self):
        response = self.import_paper(community_names=["Neuro", "Does Not Exist"])

        results = {r["name"]: r for r in response.json()["communities"]}
        self.assertTrue(results["Neuro"]["attached"])
        self.assertEqual(response.json()["article_url"], results["Neuro"]["article_url"])
        self.assertFalse(results["Does Not Exist"]["attached"])
        self.assertIsNone(results["Does Not Exist"]["article_url"])
        self.assertIn("not found", results["Does Not Exist"]["error"].lower())
        self.assertEqual(CommunityArticle.objects.count(), 1)

    def test_only_unknown_community_keeps_general_article_url(self):
        response = self.import_paper(community_names=["Does Not Exist"])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["communities"][0]["attached"])
        self.assertIn("/article/", response.json()["article_url"])
        self.assertNotIn("/community/", response.json()["article_url"])
        self.assertEqual(CommunityArticle.objects.count(), 0)

    def test_community_can_be_named_by_slug(self):
        response = self.import_paper(community_names=["gene-editing"])

        self.assertTrue(response.json()["communities"][0]["attached"])
        self.assertIn("/community/Gene%20Editing/articles/", response.json()["article_url"])

    def test_duplicate_names_attach_once(self):
        response = self.import_paper(community_names=["Neuro", "neuro", "NEURO"])

        self.assertEqual(len(response.json()["communities"]), 1)
        self.assertEqual(CommunityArticle.objects.count(), 1)

    def test_comma_joined_single_string_is_split(self):
        """Tolerate a client that sends the raw typed string as one list entry."""
        response = self.import_paper(community_names=["Neuro, Gene Editing"])

        self.assertEqual(len(response.json()["communities"]), 2)

    def test_legacy_field_still_populated_for_older_clients(self):
        response = self.import_paper(community_names=["Neuro"])

        body = response.json()
        self.assertIsNotNone(body["community_article_id"])
        self.assertEqual(body["community_submission_status"], CommunityArticle.SUBMITTED)
        self.assertIn("/community/Neuro/articles/", body["article_url"])


@override_settings(**BASE_OVERRIDES)
class ImportIntegrityTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(username="u", email="u@example.com", password="pw", is_active=True)

    def test_conflicting_identifiers_are_rejected(self):
        Article.objects.create(
            title="Paper A", abstract="", authors=[], doi="10.1111/aaa", submission_type="Public", submitter=self.user
        )
        Article.objects.create(
            title="Paper B", abstract="", authors=[], pmid="22223333", submission_type="Public", submitter=self.user
        )

        response = self.client.post(
            "/papers/import",
            json={"title": "Ambiguous", "doi": "10.1111/aaa", "pmid": "22223333"},
            headers=auth_header(self.user),
        )

        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn("different papers", response.json()["message"])
        self.assertEqual(Article.objects.count(), 2)

    def test_idempotency_key_prevents_a_duplicate_when_there_is_no_identifier(self):
        payload = {"title": "No identifiers at all", "idempotency_key": "zotero-1-ABCD-"}

        first = self.client.post("/papers/import", json=payload, headers=auth_header(self.user))
        second = self.client.post("/papers/import", json=payload, headers=auth_header(self.user))

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["article_id"], second.json()["article_id"])
        self.assertTrue(second.json()["found_existing"])
        self.assertEqual(Article.objects.count(), 1)

    def test_lookup_does_not_leak_activity_from_inaccessible_communities(self):
        from articles.models import Discussion

        owner = User.objects.create_user(username="o", email="o@example.com", password="pw", is_active=True)
        secret = Community.objects.create(name="Secret", type=Community.PRIVATE, slug="secret")
        secret.admins.add(owner)
        article = Article.objects.create(
            title="Public paper",
            abstract="",
            authors=[],
            doi="10.9999/public",
            submission_type="Public",
            submitter=owner,
        )
        Discussion.objects.create(article=article, community=secret, author=owner, topic="internal", content="x")

        response = self.client.get("/papers/lookup?doi=10.9999/public", headers=auth_header(self.user))

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["found"])
        # The discussion lives in a private community this caller has no role in.
        self.assertEqual(response.json()["total_discussions"], 0)

    def test_lookup_counts_activity_the_caller_can_see(self):
        from articles.models import Discussion

        article = Article.objects.create(
            title="Public paper",
            abstract="",
            authors=[],
            doi="10.9999/visible",
            submission_type="Public",
            submitter=self.user,
        )
        Discussion.objects.create(article=article, community=None, author=self.user, topic="open", content="x")

        response = self.client.get("/papers/lookup?doi=10.9999/visible", headers=auth_header(self.user))

        self.assertEqual(response.json()["total_discussions"], 1)


@override_settings(**BASE_OVERRIDES)
class IntegrationAuthHardeningTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(username="c", email="c@example.com", password="pw", is_active=True)
        self.redirect_uri = "http://localhost:3000/callback"

    def authorize(self, **overrides):
        payload = {
            "client_id": "scicommons-clipper",
            "redirect_uri": self.redirect_uri,
            "state": "s1",
            "code_challenge": pkce_challenge("verifier-1"),
            "code_challenge_method": "S256",
        }
        payload.update(overrides)
        return self.client.post("/auth/authorize", json=payload, headers=auth_header(self.user))

    def test_unknown_client_id_cannot_authorize(self):
        response = self.authorize(client_id="somebody-elses-client")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_unknown_client_id_cannot_start_device_auth(self):
        response = self.client.post("/auth/device/start", json={"client_id": "rogue"})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(IntegrationDeviceAuth.objects.count(), 0)

    def test_device_user_code_has_meaningful_entropy(self):
        response = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"})

        user_code = response.json()["user_code"]
        # 10 symbols from a 30-character alphabet, formatted XXXXX-XXXXX -- not 8 hex chars.
        self.assertRegex(user_code, r"^[2-9A-Z]{5}-[2-9A-Z]{5}$")
        self.assertNotRegex(user_code, r"^[0-9A-F]{4}-[0-9A-F]{4}$")

    def test_device_code_is_single_use(self):
        started = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"}).json()
        approve = self.client.post(
            "/auth/device/approve",
            json={"user_code": started["user_code"]},
            headers=auth_header(self.user),
        )
        self.assertEqual(approve.status_code, 200, approve.content)

        body = {"client_id": "scicommons-zotero", "device_code": started["device_code"]}
        first = self.client.post("/auth/device/token", json=body)
        second = self.client.post("/auth/device/token", json=body)

        self.assertEqual(first.status_code, 200, first.content)
        self.assertIn("access_token", first.json())
        self.assertEqual(second.status_code, 400)

    def test_device_cannot_be_approved_twice(self):
        started = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"}).json()
        other = User.objects.create_user(username="x", email="x@example.com", password="pw", is_active=True)

        first = self.client.post(
            "/auth/device/approve", json={"user_code": started["user_code"]}, headers=auth_header(self.user)
        )
        second = self.client.post(
            "/auth/device/approve", json={"user_code": started["user_code"]}, headers=auth_header(other)
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400, "a second user must not be able to rebind the device")
        self.assertEqual(IntegrationDeviceAuth.objects.get().user, self.user)

    def test_user_code_is_accepted_case_and_format_insensitively(self):
        started = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"}).json()
        mangled = started["user_code"].lower().replace("-", "")

        response = self.client.post(
            "/auth/device/approve", json={"user_code": mangled}, headers=auth_header(self.user)
        )

        self.assertEqual(response.status_code, 200, response.content)

    def test_poll_interval_is_enforced(self):
        started = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"}).json()
        body = {"client_id": "scicommons-zotero", "device_code": started["device_code"]}

        first = self.client.post("/auth/device/token", json=body)
        immediate_second = self.client.post("/auth/device/token", json=body)

        self.assertEqual(first.status_code, 202, first.content)
        self.assertEqual(immediate_second.status_code, 429, "polling faster than `interval` must be refused")


@override_settings(
    FRONTEND_URL="https://scicommons.org",
    DEBUG=False,
    RATELIMIT_ENABLE=False,
    CACHES=LOCMEM_CACHES,
    INTEGRATION_ALLOWED_CLIENT_IDS=["scicommons-clipper"],
    INTEGRATION_ALLOWED_REDIRECT_URIS=["https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/scicommons"],
    INTEGRATION_ALLOWED_REDIRECT_URI_PREFIXES=["https://app.example.com/cb"],
)
class RedirectAllowlistTest(TestCase):
    """With an allowlist configured and DEBUG off, nothing outside it is accepted."""

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(username="c", email="c@example.com", password="pw", is_active=True)

    def authorize(self, redirect_uri):
        return self.client.post(
            "/auth/authorize",
            json={
                "client_id": "scicommons-clipper",
                "redirect_uri": redirect_uri,
                "state": "s1",
                "code_challenge": pkce_challenge("v"),
                "code_challenge_method": "S256",
            },
            headers=auth_header(self.user),
        )

    def test_configured_redirect_is_accepted(self):
        response = self.authorize("https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/scicommons")
        self.assertEqual(response.status_code, 200, response.content)

    def test_arbitrary_extension_redirects_are_refused(self):
        for redirect_uri in (
            "chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba/cb",
            "https://someoneelses.chromiumapp.org/scicommons",
            "http://localhost:3000/callback",
        ):
            with self.subTest(redirect_uri=redirect_uri):
                self.assertEqual(self.authorize(redirect_uri).status_code, 400)

        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_prefix_does_not_match_a_sibling_domain(self):
        response = self.authorize("https://app.example.com.attacker.tld/cb")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_prefix_still_matches_its_own_paths(self):
        self.assertEqual(self.authorize("https://app.example.com/cb/done").status_code, 200)
