from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.signing import SignatureExpired, TimestampSigner
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from ninja.testing import TestClient

from users.api_auth import router
from users.models import Reputation, User


class EmailQueueTestCase(TestCase):
    """Keep API tests deterministic and prevent real Celery jobs from escaping."""

    def setUp(self):
        super().setUp()
        email_patcher = patch("users.api_auth.send_email_task.delay")
        self.mock_send_email = email_patcher.start()
        self.addCleanup(email_patcher.stop)


class SignupAPITestCase(EmailQueueTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(router)

    def test_successful_signup(self):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "confirm_password": "securepass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["message"],
            "Account created successfully. Please check your email "
            "to activate your account.",
        )

        # Check if user was created
        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_active)

        # Email delivery is asynchronous. Verify the API queues the correct job
        # instead of relying on a Celery worker to race the test process.
        self.mock_send_email.assert_called_once()
        email_job = self.mock_send_email.call_args.kwargs
        self.assertEqual(email_job["subject"], "Activate your account")
        self.assertEqual(email_job["html_template_name"], "activation_email.html")
        self.assertEqual(email_job["recipient_list"], [payload["email"]])
        self.assertEqual(email_job["context"]["name"], payload["first_name"])
        self.assertTrue(
            email_job["context"]["activation_link"].startswith(
                f"{settings.FRONTEND_URL}/auth/activate/"
            )
        )

    def test_password_mismatch(self):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "confirm_password": "differentpass",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Passwords do not match.")

    def test_existing_inactive_email(self):
        User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="pass123",
            is_active=False,
        )
        payload = {
            "username": "newuser",
            "email": "existing@example.com",
            "password": "securepass123",
            "confirm_password": "securepass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Email already registered but not activated. Please check your email "
            "for the activation link.",
        )

    def test_existing_active_email(self):
        User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="pass123",
            is_active=True,
        )
        payload = {
            "username": "newuser",
            "email": "existing@example.com",
            "password": "securepass123",
            "confirm_password": "securepass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Email is already in use.")

    def test_existing_username(self):
        User.objects.create_user(
            username="existinguser", email="existing@example.com", password="pass123"
        )
        payload = {
            "username": "existinguser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "confirm_password": "securepass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Username is already taken.")


class AccountActivationTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.signer = TimestampSigner()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
            is_active=False,
        )
        self.valid_token = self.signer.sign(self.user.pk)

    def test_successful_activation(self):
        response = self.client.post(f"/activate/{self.valid_token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Account activated successfully. You can now log in.",
        )

        # Check if user is now active
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        # Check if Reputation object was created
        self.assertTrue(Reputation.objects.filter(user=self.user).exists())

    def test_already_activated(self):
        self.user.is_active = True
        self.user.save()
        response = self.client.post(f"/activate/{self.valid_token}")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Account already activated. You can now log in.",
        )

    @patch("users.api_auth.signer.unsign")
    def test_expired_token(self, mock_unsign):
        mock_unsign.side_effect = SignatureExpired("Signature expired")
        response = self.client.post("/activate/expired_token")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Activation link expired. Please request a new one.",
        )
        mock_unsign.assert_called_once_with("expired_token", max_age=1800)

    def test_invalid_token(self):
        response = self.client.post("/activate/invalid_token")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Invalid activation link. Please request a new one.",
        )

    @patch("users.api_auth.signer.unsign")
    def test_token_expiration(self, mock_unsign):
        mock_unsign.return_value = self.user.pk
        response = self.client.post(f"/activate/{self.valid_token}")

        self.assertEqual(response.status_code, 200)
        mock_unsign.assert_called_once_with(self.valid_token, max_age=1800)


class ResendActivationAPITestCase(EmailQueueTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(router)
        self.inactive_user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="testpass123",
            first_name="John",
            is_active=False,
        )
        self.active_user = User.objects.create_user(
            username="activeuser",
            email="active@example.com",
            password="testpass123",
            is_active=True,
        )

    def test_successful_resend(self):
        response = self.client.post(f"/resend-activation/{self.inactive_user.email}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Verification link sent. Please check your email (inactive@example.com).",
        )

        self.mock_send_email.assert_called_once()
        email_job = self.mock_send_email.call_args.kwargs
        self.assertEqual(email_job["subject"], "Activate your account")
        self.assertEqual(
            email_job["html_template_name"], "resend_activation_email.html"
        )
        self.assertEqual(email_job["recipient_list"], [self.inactive_user.email])
        self.assertTrue(
            email_job["context"]["activation_link"].startswith(
                f"{settings.FRONTEND_URL}/auth/activate/"
            )
        )

    def test_already_activated(self):
        response = self.client.post(f"/resend-activation/{self.active_user.email}")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "This account is already active. You can log in now.",
        )
        self.mock_send_email.assert_not_called()

    def test_nonexistent_user(self):
        nonexistent_email = "nonexistent@example.com"
        response = self.client.post(f"/resend-activation/{nonexistent_email}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["message"],
            "No account associated with this username/email was found.",
        )
        self.mock_send_email.assert_not_called()


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.active_user = User.objects.create_user(
            username="activeuser",
            email="active@example.com",
            password="testpass123",
            is_active=True,
        )
        self.inactive_user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="testpass123",
            is_active=False,
        )

    @patch("django.contrib.auth.authenticate")
    @patch("users.api_auth.login")
    @patch("rest_framework_simplejwt.tokens.RefreshToken.for_user")
    def test_successful_login_with_username(
        self, mock_for_user, mock_login, mock_authenticate
    ):
        mock_authenticate.return_value = self.active_user
        mock_token = MagicMock()
        mock_token.access_token = "mocked-access-token"
        mock_for_user.return_value = mock_token

        payload = {"login": self.active_user.username, "password": "testpass123"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Login successful.")
        self.assertEqual(data["token"], "mocked-access-token")

        # Check for cookies
        self.assertIn("accessToken", response.cookies)
        self.assertIn("refreshToken", response.cookies)

    @patch("django.contrib.auth.authenticate")
    @patch("users.api_auth.login")
    @patch("rest_framework_simplejwt.tokens.RefreshToken.for_user")
    def test_successful_login_with_email(
        self, mock_for_user, mock_login, mock_authenticate
    ):
        mock_authenticate.return_value = self.active_user
        mock_token = MagicMock()
        mock_token.access_token = "mocked-access-token"
        mock_for_user.return_value = mock_token

        payload = {"login": self.active_user.email, "password": "testpass123"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Login successful.")
        self.assertEqual(data["token"], "mocked-access-token")

    def test_inactive_account(self):
        payload = {"login": self.inactive_user.username, "password": "testpass123"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(
            data["message"],
            "This account is inactive. Please activate your account "
            "(inactive@example.com) first.",
        )

    def test_nonexistent_user(self):
        payload = {"login": "nonexistent@example.com", "password": "testpass123"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(
            data["message"], "No account found with the provided username/email."
        )

    @patch("django.contrib.auth.authenticate")
    def test_invalid_password(self, mock_authenticate):
        mock_authenticate.return_value = None
        payload = {"login": self.active_user.username, "password": "wrongpassword"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data["message"], "Invalid password. Please try again.")

    @patch("django.contrib.auth.authenticate")
    @patch("users.api_auth.login")
    @patch("rest_framework_simplejwt.tokens.RefreshToken.for_user")
    def test_cookie_settings(self, mock_for_user, mock_login, mock_authenticate):
        mock_authenticate.return_value = self.active_user
        mock_token = MagicMock()
        mock_token.access_token = "mocked-access-token"
        mock_for_user.return_value = mock_token

        payload = {"login": self.active_user.username, "password": "testpass123"}
        response = self.client.post("/login", json=payload)
        self.assertEqual(response.status_code, 200)

        # Check access token cookie
        self.assertIn("accessToken", response.cookies)
        access_cookie = response.cookies["accessToken"]
        self.assertTrue(access_cookie["httponly"])
        self.assertFalse(access_cookie["secure"])
        self.assertEqual(access_cookie["samesite"], "None")
        self.assertEqual(access_cookie["max-age"], 120 * 60)  # 2 hours

        # Check refresh token cookie
        self.assertIn("refreshToken", response.cookies)
        refresh_cookie = response.cookies["refreshToken"]
        self.assertTrue(refresh_cookie["httponly"])
        self.assertFalse(refresh_cookie["secure"])
        self.assertEqual(refresh_cookie["samesite"], "None")
        self.assertEqual(refresh_cookie["max-age"], 7 * 24 * 60 * 60)  # 7 days

    # @patch("django.contrib.auth.authenticate")
    # @patch("users.api_auth.login")
    # def test_authentication_called(self, mock_login, mock_authenticate):
    #     mock_authenticate.return_value = self.active_user

    #     # Create a mock request object
    #     mock_request = MagicMock()
    #     mock_request.session = {}

    #     payload = {"login": self.active_user.username, "password": "testpass123"}
    #     self.client.post("/login", json=payload)

    #     # Check that authenticate was called with correct arguments
    #     mock_authenticate.assert_called_once_with(
    #         username=self.active_user.username, password="testpass123"
    #     )

    #     # Check that login was called
    #     mock_login.assert_called_once()

    #     # Check the arguments of the login call
    #     call_args = mock_login.call_args
    #     self.assertEqual(
    #         call_args[0][1], self.active_user
    #     )  # Second argument should be the user object


class ForgotPasswordAPITestCase(EmailQueueTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
            first_name="John",
        )

    def test_successful_request(self):
        response = self.client.post(f"/forgot-password/{self.user.email}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Password reset link has been sent to your email.",
        )

        self.mock_send_email.assert_called_once()
        email_job = self.mock_send_email.call_args.kwargs
        self.assertEqual(email_job["subject"], "Password Reset Request")
        self.assertEqual(email_job["html_template_name"], "password_reset_email.html")
        self.assertEqual(email_job["recipient_list"], [self.user.email])
        self.assertEqual(email_job["context"]["name"], self.user.first_name)
        self.assertTrue(
            email_job["context"]["reset_link"].startswith(
                f"{settings.FRONTEND_URL}/auth/resetpassword/"
            )
        )

    def test_nonexistent_user(self):
        nonexistent_email = "nonexistent@example.com"
        response = self.client.post(f"/forgot-password/{nonexistent_email}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["message"], "No user found with this email address."
        )

        self.mock_send_email.assert_not_called()

    def test_reset_link_structure(self):
        response = self.client.post(f"/forgot-password/{self.user.email}")

        self.assertEqual(response.status_code, 200)

        self.mock_send_email.assert_called_once()
        reset_link = self.mock_send_email.call_args.kwargs["context"]["reset_link"]

        # Verify the structure of the reset link
        link_parts = reset_link.split("/")
        self.assertGreater(len(link_parts), 2, "Reset link should have multiple parts")
        self.assertEqual(
            link_parts[-2],
            "resetpassword",
            "The penultimate part of the link should match the frontend route",
        )

        # Check that the link contains a signed UID
        uid_part = link_parts[-1]
        self.assertTrue(len(uid_part) > 0, "UID part of reset link is empty")
        self.assertRegex(
            uid_part,
            r"^[A-Za-z0-9_:-]+$",
            "UID should only contain alphanumeric characters, underscores, "
            "colons, and hyphens",
        )


class ResetPasswordTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.signer = TimestampSigner()
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="oldpassword"
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    def generate_token(self, uid):
        return self.signer.sign(uid)

    def test_successful_reset(self):
        token = self.generate_token(self.uid)
        payload = {
            "password": "newpassword123",
            "confirm_password": "newpassword123",
        }
        response = self.client.post(f"/reset-password/{token}", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Password reset successfully. You can now log in with your new password.",
        )

        # Verify that the password has been changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword123"))

    @patch("users.api_auth.signer.unsign")
    def test_expired_token(self, mock_unsign):
        token = self.generate_token(self.uid)
        mock_unsign.side_effect = SignatureExpired("Signature expired")
        payload = {
            "password": "newpassword123",
            "confirm_password": "newpassword123",
        }
        response = self.client.post(f"/reset-password/{token}", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Password reset link expired. Please request a new one.",
        )
        mock_unsign.assert_called_once_with(token, max_age=3600)

    def test_invalid_token(self):
        payload = {
            "password": "newpassword123",
            "confirm_password": "newpassword123",
        }
        response = self.client.post("/reset-password/invalid_token", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "Invalid password reset link. Please request a new one.",
        )

    def test_password_mismatch(self):
        token = self.generate_token(self.uid)
        payload = {
            "password": "newpassword123",
            "confirm_password": "differentpassword123",
        }
        response = self.client.post(f"/reset-password/{token}", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "Passwords do not match. Please try again."
        )
