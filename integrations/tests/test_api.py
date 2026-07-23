import base64
import hashlib

from django.test import TestCase, override_settings
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from articles.models import Article
from integrations.api import router
from integrations.models import IntegrationDeviceAuth
from users.models import User


def auth_header(user):
    token = RefreshToken.for_user(user).access_token
    return {"Authorization": f"Bearer {token}"}


def pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@override_settings(DEBUG=True, FRONTEND_URL="http://localhost:3000")
class IntegrationsAPITestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="clipperuser",
            email="clipper@example.com",
            password="password123",
            is_active=True,
        )

    def test_import_is_idempotent_by_doi(self):
        payload = {
            "title": "A clipped paper",
            "abstract": "A useful abstract.",
            "authors": [{"label": "Ada Lovelace", "value": "Ada Lovelace"}],
            "doi": "https://doi.org/10.1234/example",
            "url": "https://example.org/paper",
            "submission_type": "Public",
        }

        first = self.client.post("/papers/import", json=payload, headers=auth_header(self.user))
        second = self.client.post("/papers/import", json=payload, headers=auth_header(self.user))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["found_existing"])
        self.assertTrue(second.json()["found_existing"])
        self.assertEqual(first.json()["article_id"], second.json()["article_id"])
        self.assertEqual(Article.objects.filter(doi="10.1234/example").count(), 1)

    def test_private_article_lookup_hidden_from_anonymous(self):
        Article.objects.create(
            title="Private paper",
            abstract="Private abstract",
            authors=[],
            doi="10.5555/private",
            submission_type="Private",
            submitter=self.user,
        )

        anonymous = self.client.get("/papers/lookup?doi=10.5555/private")
        authenticated = self.client.get("/papers/lookup?doi=10.5555/private", headers=auth_header(self.user))

        self.assertEqual(anonymous.status_code, 200)
        self.assertFalse(anonymous.json()["found"])
        self.assertEqual(authenticated.status_code, 200)
        self.assertTrue(authenticated.json()["found"])

    def test_import_does_not_reuse_another_users_private_article(self):
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="password123",
            is_active=True,
        )
        private_article = Article.objects.create(
            title="Other private paper",
            abstract="Private abstract",
            authors=[],
            doi="10.7777/private",
            submission_type="Private",
            submitter=other_user,
        )

        response = self.client.post(
            "/papers/import",
            json={
                "title": "My copy of the paper",
                "abstract": "Visible only to me.",
                "authors": [],
                "doi": "10.7777/private",
                "submission_type": "Private",
            },
            headers=auth_header(self.user),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["found_existing"])
        self.assertNotEqual(response.json()["article_id"], private_article.id)
        self.assertEqual(Article.objects.filter(doi="10.7777/private").count(), 2)

    def test_pkce_exchange_is_single_use(self):
        verifier = "a" * 64
        redirect_uri = "http://localhost:3000/callback"
        authorize = self.client.post(
            "/auth/authorize",
            json={
                "client_id": "scicommons-clipper",
                "redirect_uri": redirect_uri,
                "state": "state-1",
                "code_challenge": pkce_challenge(verifier),
                "code_challenge_method": "S256",
            },
            headers=auth_header(self.user),
        )

        self.assertEqual(authorize.status_code, 200)
        code = authorize.json()["code"]
        exchange_payload = {
            "client_id": "scicommons-clipper",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        }

        first = self.client.post("/auth/exchange", json=exchange_payload)
        second = self.client.post("/auth/exchange", json=exchange_payload)

        self.assertEqual(first.status_code, 200)
        self.assertIn("access_token", first.json())
        self.assertEqual(second.status_code, 400)

    def test_device_auth_flow_returns_token_after_approval(self):
        start = self.client.post("/auth/device/start", json={"client_id": "scicommons-zotero"})
        self.assertEqual(start.status_code, 200)
        pending = self.client.post(
            "/auth/device/token",
            json={
                "client_id": "scicommons-zotero",
                "device_code": start.json()["device_code"],
            },
        )
        self.assertEqual(pending.status_code, 202)

        approve = self.client.post(
            "/auth/device/approve",
            json={"user_code": start.json()["user_code"]},
            headers=auth_header(self.user),
        )
        self.assertEqual(approve.status_code, 200)

        token = self.client.post(
            "/auth/device/token",
            json={
                "client_id": "scicommons-zotero",
                "device_code": start.json()["device_code"],
            },
        )
        self.assertEqual(token.status_code, 200)
        self.assertEqual(token.json()["user"]["username"], "clipperuser")
        self.assertEqual(IntegrationDeviceAuth.objects.get().status, IntegrationDeviceAuth.CONSUMED)
