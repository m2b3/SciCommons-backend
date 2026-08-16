"""Guards the seam created by stacking #168 on top of #167.

#167 shipped the `/extension/*` surface; #168 added the generalised `/auth/*` surface and made
`/extension/*` aliases over the same handlers. The browser extension in `extension/` still calls
`/api/integrations/extension/exchange`, while the frontend page it opens (#363) authorises via
`/api/integrations/auth/authorize`. Nothing in either PR's own suite covers that crossing: each
tests its own surface end to end. If a future change gives the two surfaces separate code
storage, the extension breaks silently and only these tests would catch it.
"""

import base64
import hashlib

from django.test import TestCase, override_settings
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from integrations.api import router
from users.models import User

REDIRECT_URI = "https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/scicommons"
CLIENT_ID = "scicommons-clipper"  # matches extension/background.js
VERIFIER = "x" * 64


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@override_settings(
    INTEGRATION_ALLOWED_CLIENT_IDS=[CLIENT_ID, "scicommons-zotero"],
    INTEGRATION_ALLOWED_REDIRECT_URIS=[REDIRECT_URI],
)
class StackedAuthSurfaceTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="clipperuser",
            email="clipper@example.com",
            password="password123",
            is_active=True,
        )
        self.headers = {"Authorization": f"Bearer {RefreshToken.for_user(self.user).access_token}"}

    def authorize(self, path):
        return self.client.post(
            path,
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "state": "opaque-state-value",
                "code_challenge": pkce_challenge(VERIFIER),
                "code_challenge_method": "S256",
            },
            headers=self.headers,
        )

    def exchange(self, path, code):
        return self.client.post(
            path,
            json={
                "client_id": CLIENT_ID,
                "code": code,
                "code_verifier": VERIFIER,
                "redirect_uri": REDIRECT_URI,
            },
        )

    def test_code_from_auth_surface_is_redeemable_on_extension_surface(self):
        """The exact path the shipped extension takes after #363 lands."""
        authorized = self.authorize("/auth/authorize")
        self.assertEqual(authorized.status_code, 200, authorized.content)

        exchanged = self.exchange("/extension/exchange", authorized.json()["code"])
        self.assertEqual(exchanged.status_code, 200, exchanged.content)
        body = exchanged.json()
        self.assertTrue(body["access_token"])
        self.assertTrue(body["refresh_token"])
        self.assertEqual(body["user"]["username"], "clipperuser")

    def test_code_from_extension_surface_is_redeemable_on_auth_surface(self):
        """The reverse crossing, so the aliases cannot drift apart in one direction only."""
        authorized = self.authorize("/extension/authorize")
        self.assertEqual(authorized.status_code, 200, authorized.content)

        exchanged = self.exchange("/auth/exchange", authorized.json()["code"])
        self.assertEqual(exchanged.status_code, 200, exchanged.content)

    def test_state_is_echoed_back(self):
        """extension/background.js rejects the callback unless `state` comes back and matches."""
        for path in ("/auth/authorize", "/extension/authorize"):
            with self.subTest(path=path):
                response = self.authorize(path)
                self.assertEqual(response.json()["state"], "opaque-state-value")

    def test_a_code_is_single_use_across_surfaces(self):
        """Redeeming on one surface must consume the code for the other one too."""
        code = self.authorize("/auth/authorize").json()["code"]

        self.assertEqual(self.exchange("/extension/exchange", code).status_code, 200)
        self.assertEqual(self.exchange("/auth/exchange", code).status_code, 400)
