from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import AccessToken

from users.api import router
from users.config_constants import UserConfigKey
from users.models import User, UserSetting
from users.settings_cache import get_user_settings, get_user_settings_from_cache


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class BulkSettingsUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="settings-user", email="settings@example.com", password=None)
        self.client = TestClient(router)
        self.headers = {"Authorization": f"Bearer {AccessToken.for_user(self.user)}"}
        self.email_key = UserConfigKey.ENABLE_EMAIL_NOTIFICATIONS
        self.sound_key = UserConfigKey.ENABLE_SOUND_ON_DISCUSSION_NOTIFICATION
        UserSetting.objects.create(user=self.user, config_name=self.email_key, value=False)
        cache.clear()
        self.addCleanup(cache.clear)
        self.original_settings = get_user_settings(self.user.id)

    def update_settings(self, sound_value):
        return self.client.put(
            "/settings",
            headers=self.headers,
            json={
                "settings": [
                    {"config_name": self.email_key, "value": True},
                    {"config_name": self.sound_key, "value": sound_value},
                ]
            },
        )

    def assert_original_settings(self):
        self.assertFalse(UserSetting.objects.get(user=self.user, config_name=self.email_key).value)
        self.assertFalse(UserSetting.objects.filter(user=self.user, config_name=self.sound_key).exists())
        self.assertEqual(get_user_settings_from_cache(self.user.id), self.original_settings)

    def test_later_invalid_value_does_not_apply_earlier_update(self):
        response = self.update_settings("not-a-boolean")
        self.assertEqual(response.status_code, 400)
        self.assert_original_settings()

    def test_later_database_error_rolls_back_earlier_update(self):
        update_or_create = UserSetting.objects.update_or_create

        def fail_second_update(**kwargs):
            if kwargs["config_name"] == self.sound_key:
                raise DatabaseError("Simulated database failure")
            return update_or_create(**kwargs)

        with patch("users.api.UserSetting.objects.update_or_create", side_effect=fail_second_update):
            response = self.update_settings(True)
        self.assertEqual(response.status_code, 500)
        self.assert_original_settings()

    def test_successful_update_refreshes_both_settings(self):
        response = self.update_settings(True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_count"], 2)
        self.assertIsNone(get_user_settings_from_cache(self.user.id))
        self.assertTrue(UserSetting.objects.get(user=self.user, config_name=self.email_key).value)
        self.assertTrue(UserSetting.objects.get(user=self.user, config_name=self.sound_key).value)
        refreshed_settings = get_user_settings(self.user.id)
        self.assertTrue(refreshed_settings[self.email_key])
        self.assertTrue(refreshed_settings[self.sound_key])
