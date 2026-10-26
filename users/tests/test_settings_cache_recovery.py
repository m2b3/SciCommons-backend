from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError
from django.test import TestCase, override_settings

from users.config_constants import UserConfigKey
from users.models import User, UserSetting
from users.settings_cache import get_user_settings, get_user_settings_from_cache


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class SettingsCacheRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cache-user", email="cache@example.com", password=None)
        self.email_key = UserConfigKey.ENABLE_EMAIL_NOTIFICATIONS
        cache.clear()
        self.addCleanup(cache.clear)

    def test_database_recovery_restores_saved_preferences_on_next_read(self):
        UserSetting.objects.create(user=self.user, config_name=self.email_key, value=True)
        with patch("users.models.UserSetting.objects.filter", side_effect=OperationalError("Temporary DB failure")):
            fallback = get_user_settings(self.user.id)
        self.assertFalse(fallback[self.email_key])
        recovered = get_user_settings(self.user.id)
        self.assertTrue(recovered[self.email_key])
        self.assertEqual(get_user_settings_from_cache(self.user.id), recovered)

    def test_successful_read_is_cached(self):
        UserSetting.objects.create(user=self.user, config_name=self.email_key, value=True)
        settings = get_user_settings(self.user.id)
        self.assertTrue(settings[self.email_key])
        with self.assertNumQueries(0):
            self.assertEqual(get_user_settings(self.user.id), settings)

    def test_successful_read_without_custom_settings_caches_defaults(self):
        settings = get_user_settings(self.user.id)
        self.assertFalse(settings[self.email_key])
        self.assertEqual(get_user_settings_from_cache(self.user.id), settings)
