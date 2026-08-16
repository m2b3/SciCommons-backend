"""Security regression tests for the browser-extension integration endpoints.

Each test corresponds to a specific audited defect in PR 167. The most important is
`test_import_cannot_reach_another_users_private_article` -- `import_paper` applied no
visibility rule, so any authenticated user could reach another user's private article by
identifier, have their identifiers and PDF link written onto it, attach it to a community, and
read back its title and slug. The absence of exactly this test is why the bug shipped.

The class-level overrides matter:
  * `CACHES` -> locmem so the idempotency cache does not read or write the shared dev Redis.
  * `RATELIMIT_ENABLE=False` so the 20/min limits on the auth endpoints (which are keyed off a
    constant IP under TestClient) do not make these tests order-dependent.
"""

import base64
import hashlib
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase, override_settings

from articles.models import Article, ArticlePDF
from communities.models import CommunityArticle
from integrations.api import router
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken
from integrations.models import IntegrationAuthCode
from users.models import User

LOCMEM_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def auth_headers(user):
    token = str(RefreshToken.for_user(user).access_token)
    return {"Authorization": f"Bearer {token}"}


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@override_settings(
    FRONTEND_URL="http://localhost:3000",
    DEBUG=True,
    RATELIMIT_ENABLE=False,
    CACHES=LOCMEM_CACHES,
)
class PaperImportSecurityTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="password123", is_active=True
        )
        self.stranger = User.objects.create_user(
            username="stranger", email="stranger@example.com", password="password123", is_active=True
        )

    def test_import_cannot_reach_another_users_private_article(self):
        private = Article.objects.create(
            title="Owner's unpublished work",
            abstract="Secret abstract",
            authors=[],
            doi="10.1234/secret",
            submission_type="Private",
            submitter=self.owner,
        )

        response = self.client.post(
            "/papers/import",
            json={
                "title": "Attacker supplied title",
                "abstract": "",
                "doi": "10.1234/secret",
                "pmid": "99887766",
                "pdf_link": "https://attacker.example/evil.pdf",
            },
            headers=auth_headers(self.stranger),
        )

        # #167 answered this with a 409, relying on a global unique constraint on `doi`. The
        # stacked importer (#168) instead gives the caller their own row, so the assertion moves
        # from "refused" to "did not touch or reveal the owner's article" -- which is the
        # security property this test exists to protect, and it still holds.
        self.assertEqual(response.status_code, 200, response.content)

        body = response.json()
        self.assertFalse(body["found_existing"])
        self.assertNotEqual(body["article_id"], private.id)

        # The response must not disclose anything about the private article.
        self.assertNotIn("Owner's unpublished work", response.content.decode())
        self.assertNotIn(private.slug, response.content.decode())

        # And the article itself must be untouched.
        private.refresh_from_db()
        self.assertEqual(private.title, "Owner's unpublished work")
        self.assertIsNone(private.pmid)
        self.assertEqual(private.title, "Owner's unpublished work")
        self.assertFalse(ArticlePDF.objects.filter(article=private).exists())
        self.assertFalse(CommunityArticle.objects.filter(article=private).exists())

    def test_owner_can_still_import_their_own_private_article(self):
        """The visibility rule must not lock the legitimate owner out."""
        Article.objects.create(
            title="Owner's unpublished work",
            abstract="Secret abstract",
            authors=[],
            doi="10.1234/secret",
            submission_type="Private",
            submitter=self.owner,
        )

        response = self.client.post(
            "/papers/import",
            json={"title": "Owner's unpublished work", "doi": "10.1234/secret", "pmid": "12345678"},
            headers=auth_headers(self.owner),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["found_existing"])
        self.assertEqual(response.json()["pmid"], "12345678")

    def test_conflicting_identifiers_are_rejected_without_mutating_anything(self):
        by_doi = Article.objects.create(
            title="Paper A",
            abstract="",
            authors=[],
            doi="10.1111/aaa",
            submission_type="Public",
            submitter=self.owner,
        )
        by_pmid = Article.objects.create(
            title="Paper B",
            abstract="",
            authors=[],
            pmid="22223333",
            submission_type="Public",
            submitter=self.owner,
        )

        response = self.client.post(
            "/papers/import",
            json={"title": "Ambiguous", "doi": "10.1111/aaa", "pmid": "22223333"},
            headers=auth_headers(self.stranger),
        )

        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn("different papers", response.json()["message"])

        by_doi.refresh_from_db()
        by_pmid.refresh_from_db()
        self.assertIsNone(by_doi.pmid)
        self.assertIsNone(by_pmid.doi)
        self.assertEqual(Article.objects.count(), 2)

    def test_malformed_pmid_is_rejected_rather_than_coerced(self):
        response = self.client.post(
            "/papers/import",
            json={"title": "Bad PMID", "pmid": "abc123"},
            headers=auth_headers(self.stranger),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Article.objects.count(), 0)

    def test_pmc_id_is_not_silently_treated_as_a_pmid(self):
        response = self.client.post(
            "/papers/import",
            json={"title": "PMC not PMID", "pmid": "PMC3456789"},
            headers=auth_headers(self.stranger),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Article.objects.count(), 0)

    def test_prefixed_pmid_is_still_accepted(self):
        response = self.client.post(
            "/papers/import",
            json={"title": "Prefixed PMID", "pmid": "PMID:12345678"},
            headers=auth_headers(self.stranger),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["pmid"], "12345678")

    def test_malformed_url_is_rejected(self):
        for bad_url in ("javascript:alert(1)", "abc", "../../etc/passwd"):
            with self.subTest(url=bad_url):
                response = self.client.post(
                    "/papers/import",
                    json={"title": "Bad URL", "url": bad_url},
                    headers=auth_headers(self.stranger),
                )
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Article.objects.count(), 0)

    def test_lookup_rejects_malformed_identifiers(self):
        response = self.client.get("/papers/lookup?pmid=abc123")
        self.assertEqual(response.status_code, 400, response.content)

    def test_idempotency_key_returns_the_same_article(self):
        payload = {
            "title": "Keyed import with no identifiers",
            "abstract": "",
            "idempotency_key": "fixed-key-1",
        }

        first = self.client.post("/papers/import", json=payload, headers=auth_headers(self.stranger))
        second = self.client.post("/papers/import", json=payload, headers=auth_headers(self.stranger))

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["article_id"], second.json()["article_id"])
        self.assertTrue(second.json()["found_existing"])
        # Without the key this payload carries no identifier to dedupe on, so the second
        # request would otherwise have created a second article.
        self.assertEqual(Article.objects.count(), 1)

    def test_idempotency_key_is_scoped_per_user(self):
        payload = {"title": "Same key, different user", "idempotency_key": "shared-key"}

        self.client.post("/papers/import", json=payload, headers=auth_headers(self.stranger))
        other = self.client.post("/papers/import", json=payload, headers=auth_headers(self.owner))

        self.assertEqual(other.status_code, 200, other.content)
        self.assertFalse(other.json()["found_existing"])
        self.assertEqual(Article.objects.count(), 2)

    def test_concurrent_create_returns_the_winning_article(self):
        """Simulates the TOCTOU: the row appears between the lookup and the insert."""
        existing = Article.objects.create(
            title="Winner",
            abstract="",
            authors=[],
            doi="10.5555/race",
            submission_type="Public",
            submitter=self.owner,
        )

        from integrations import api as integrations_api

        # Retargeted while stacking: #168 renamed this helper to `_identifier_matches` and
        # returns a plain {identifier: article} dict instead of a (article, dict) tuple. The
        # property under test is unchanged -- the importer must not create a duplicate when the
        # row materialises between the lookup and the insert. #168 holds that with a Postgres
        # advisory lock keyed on the identifier rather than with a unique constraint.
        real_resolve = integrations_api._identifier_matches
        calls = {"n": 0}

        def flaky_resolve(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                # Pretend the row is not visible yet, forcing the create path.
                return {}
            return real_resolve(*args, **kwargs)

        with patch.object(integrations_api, "_identifier_matches", side_effect=flaky_resolve):
            response = self.client.post(
                "/papers/import",
                json={"title": "Loser", "doi": "10.5555/race"},
                headers=auth_headers(self.stranger),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["found_existing"])
        self.assertEqual(response.json()["article_id"], existing.id)
        self.assertEqual(Article.objects.filter(doi="10.5555/race").count(), 1)

    def test_unrelated_integrity_error_is_not_swallowed(self):
        """Guard against the IntegrityError catch masking a genuine failure.

        With no identifiers there is no "winning" row to refetch, so the error must be
        re-raised rather than turned into a success. Through the mounted API this surfaces as
        409 DATA_CONFLICT via the handler in myapp/api.py; TestClient(router) bypasses those
        handlers and reports 500. Either way it must not be a 200, and no article may exist.
        """
        with patch.object(Article.objects, "create", side_effect=IntegrityError("unrelated")):
            response = self.client.post(
                "/papers/import",
                json={"title": "No identifiers, so no winner to refetch"},
                headers=auth_headers(self.stranger),
            )

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(Article.objects.count(), 0)


@override_settings(
    FRONTEND_URL="http://localhost:3000",
    DEBUG=True,
    RATELIMIT_ENABLE=False,
    CACHES=LOCMEM_CACHES,
)
class ExtensionAuthSecurityTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="clipper", email="clipper@example.com", password="password123", is_active=True
        )
        self.redirect_uri = "http://localhost:3000/extension-callback"

    def authorize(self, **overrides):
        payload = {
            "client_id": "scicommons-clipper",
            "redirect_uri": self.redirect_uri,
            "state": "state-1",
            "code_challenge": pkce_challenge("verifier-1"),
            "code_challenge_method": "S256",
        }
        payload.update(overrides)
        return self.client.post("/extension/authorize", json=payload, headers=auth_headers(self.user))

    def test_plain_pkce_method_is_rejected(self):
        response = self.authorize(code_challenge_method="plain", code_challenge="verifier-1")

        self.assertIn(response.status_code, (400, 422), response.content)
        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_unknown_client_id_is_rejected(self):
        response = self.authorize(client_id="somebody-elses-extension")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_exchange_requires_redirect_uri(self):
        authorize = self.authorize()
        self.assertEqual(authorize.status_code, 200, authorize.content)

        response = self.client.post(
            "/extension/exchange",
            json={
                "client_id": "scicommons-clipper",
                "code": authorize.json()["code"],
                "code_verifier": "verifier-1",
            },
        )

        self.assertIn(response.status_code, (400, 422), response.content)
        self.assertFalse(IntegrationAuthCode.objects.first().is_used)

    def test_exchange_rejects_mismatched_redirect_uri(self):
        authorize = self.authorize()

        response = self.client.post(
            "/extension/exchange",
            json={
                "client_id": "scicommons-clipper",
                "code": authorize.json()["code"],
                "code_verifier": "verifier-1",
                "redirect_uri": "http://localhost:3000/somewhere-else",
            },
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(IntegrationAuthCode.objects.first().is_used)

    def test_exchange_refuses_a_stored_plain_challenge(self):
        """Defence in depth for codes minted before `plain` was removed."""
        authorize = self.authorize()
        code_row = IntegrationAuthCode.objects.get()
        code_row.code_challenge_method = "plain"
        code_row.code_challenge = "verifier-1"
        code_row.save(update_fields=["code_challenge_method", "code_challenge"])

        response = self.client.post(
            "/extension/exchange",
            json={
                "client_id": "scicommons-clipper",
                "code": authorize.json()["code"],
                "code_verifier": "verifier-1",
                "redirect_uri": self.redirect_uri,
            },
        )

        self.assertEqual(response.status_code, 400, response.content)
        code_row.refresh_from_db()
        self.assertFalse(code_row.is_used)


@override_settings(
    FRONTEND_URL="https://scicommons.org",
    DEBUG=False,
    RATELIMIT_ENABLE=False,
    CACHES=LOCMEM_CACHES,
    INTEGRATION_ALLOWED_CLIENT_IDS=["scicommons-clipper"],
    INTEGRATION_ALLOWED_REDIRECT_URIS=["https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/scicommons"],
    INTEGRATION_ALLOWED_REDIRECT_URI_PREFIXES=["https://app.example.com/cb"],
)
class ExtensionRedirectAllowlistTest(TestCase):
    """With an allowlist configured, nothing outside it is accepted -- DEBUG off."""

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="clipper", email="clipper@example.com", password="password123", is_active=True
        )

    def authorize(self, redirect_uri):
        return self.client.post(
            "/extension/authorize",
            json={
                "client_id": "scicommons-clipper",
                "redirect_uri": redirect_uri,
                "state": "state-1",
                "code_challenge": pkce_challenge("verifier-1"),
                "code_challenge_method": "S256",
            },
            headers=auth_headers(self.user),
        )

    def test_configured_redirect_uri_is_accepted(self):
        response = self.authorize("https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/scicommons")
        self.assertEqual(response.status_code, 200, response.content)

    def test_arbitrary_chrome_extension_redirect_is_rejected(self):
        for redirect_uri in (
            "chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba/callback",
            "https://someoneelsesextensionid.chromiumapp.org/scicommons",
            "https://x@evil.chromiumapp.org/scicommons",
            "http://localhost:3000/extension-callback",
        ):
            with self.subTest(redirect_uri=redirect_uri):
                response = self.authorize(redirect_uri)
                self.assertEqual(response.status_code, 400, response.content)

        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_prefix_allowlist_does_not_match_a_sibling_domain(self):
        """`startswith` on the raw URI used to authorise app.example.com.attacker.tld."""
        response = self.authorize("https://app.example.com.attacker.tld/cb")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(IntegrationAuthCode.objects.count(), 0)

    def test_configured_prefix_still_matches_its_own_paths(self):
        response = self.authorize("https://app.example.com/cb/done")
        self.assertEqual(response.status_code, 200, response.content)
