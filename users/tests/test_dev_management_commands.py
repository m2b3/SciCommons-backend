from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from articles.models import Article
from communities.models import Community
from posts.models import Post
from users.models import User


@override_settings(ENVIRONMENT="local", DEBUG=True)
class SeedDevDataCommandTest(TestCase):
    @patch.dict(
        "users.management.dev_database.connection.settings_dict",
        {"NAME": "scicommons_dev"},
    )
    def test_seed_is_idempotent(self):
        call_command("seed_dev_data", stdout=StringIO())
        call_command("seed_dev_data", stdout=StringIO())

        self.assertEqual(
            User.objects.filter(username__startswith="synthetic-").count(), 2
        )
        self.assertEqual(
            Community.objects.filter(slug="synthetic-open-science").count(), 1
        )
        self.assertEqual(
            Article.objects.filter(
                slug="synthetic-reproducible-research"
            ).count(),
            1,
        )
        self.assertEqual(
            Post.objects.filter(title="Synthetic development discussion").count(),
            1,
        )

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_seed_refuses_non_development_environment(self):
        with self.assertRaises(CommandError):
            call_command("seed_dev_data", stdout=StringIO())

    @patch.dict(
        "users.management.dev_database.connection.settings_dict",
        {"NAME": "scicommons_dev"},
    )
    def test_reset_requires_confirmation(self):
        with self.assertRaisesMessage(CommandError, "Re-run with --yes"):
            call_command("reset_dev_data", stdout=StringIO())
