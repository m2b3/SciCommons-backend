import base64
import hashlib

from django.test import TestCase, override_settings
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from articles.models import Article
from integrations.api import router
from users.models import ExtensionAuthCode, User


def auth_headers(user):
    token = str(RefreshToken.for_user(user).access_token)
    return {"Authorization": f"Bearer {token}"}


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@override_settings(FRONTEND_URL="http://localhost:3000", DEBUG=True)
class PaperIntegrationAPITest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="clipper",
            email="clipper@example.com",
            password="password123",
            is_active=True,
        )

    def test_import_is_idempotent_by_doi(self):
        payload = {
            "title": "A DOI Paper",
            "abstract": "Abstract",
            "authors": [{"label": "Jane Doe", "value": "Jane Doe"}],
            "doi": "https://doi.org/10.1234/Example",
            "url": "https://publisher.example/paper",
        }

        first = self.client.post("/papers/import", json=payload, headers=auth_headers(self.user))
        second = self.client.post("/papers/import", json=payload, headers=auth_headers(self.user))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["found_existing"])
        self.assertTrue(second.json()["found_existing"])
        self.assertEqual(first.json()["article_id"], second.json()["article_id"])
        self.assertEqual(Article.objects.filter(doi="10.1234/example").count(), 1)

    def test_lookup_hides_private_article_from_anonymous_user(self):
        Article.objects.create(
            title="Private DOI Paper",
            abstract="Private abstract",
            authors=[],
            doi="10.1234/private",
            submission_type="Private",
            submitter=self.user,
        )

        response = self.client.get("/papers/lookup?doi=10.1234/private")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["found"])

    def test_extension_code_exchange_is_single_use_with_pkce(self):
        verifier = "test-verifier"
        authorize_payload = {
            "client_id": "scicommons-clipper",
            "redirect_uri": "http://localhost:3000/extension-callback",
            "state": "state-1",
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }

        authorize = self.client.post(
            "/extension/authorize",
            json=authorize_payload,
            headers=auth_headers(self.user),
        )
        self.assertEqual(authorize.status_code, 200)
        self.assertEqual(ExtensionAuthCode.objects.count(), 1)

        exchange_payload = {
            "client_id": "scicommons-clipper",
            "code": authorize.json()["code"],
            "code_verifier": verifier,
            "redirect_uri": authorize_payload["redirect_uri"],
        }
        exchange = self.client.post("/extension/exchange", json=exchange_payload)
        reuse = self.client.post("/extension/exchange", json=exchange_payload)

        self.assertEqual(exchange.status_code, 200)
        self.assertIn("access_token", exchange.json())
        self.assertEqual(reuse.status_code, 400)
