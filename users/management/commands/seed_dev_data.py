"""Create a small, deterministic, synthetic development dataset."""

from django.core.management.base import BaseCommand
from django.db import transaction

from articles.models import Article
from communities.models import Community, CommunityArticle, Membership
from posts.models import Post
from users.management.dev_database import require_local_development_database
from users.models import User


class Command(BaseCommand):
    help = "Create an idempotent synthetic dataset in scicommons_dev"

    @transaction.atomic
    def handle(self, *args, **options):
        require_local_development_database()

        admin, admin_created = User.objects.get_or_create(
            username="synthetic-admin",
            defaults={
                "email": "synthetic-admin@scicommons.invalid",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin_created:
            admin.set_password("synthetic-dev-only")
            admin.save(update_fields=["password"])

        contributor, contributor_created = User.objects.get_or_create(
            username="synthetic-contributor",
            defaults={
                "email": "synthetic-contributor@scicommons.invalid",
                "is_active": True,
            },
        )
        if contributor_created:
            contributor.set_password("synthetic-dev-only")
            contributor.save(update_fields=["password"])

        community, _ = Community.objects.get_or_create(
            slug="synthetic-open-science",
            defaults={
                "name": "Synthetic Open Science",
                "description": "Synthetic records for local development only.",
                "type": Community.PUBLIC,
                "rules": ["Use only synthetic data in this development community."],
                "about": {"purpose": "Local SciCommons feature testing"},
            },
        )
        community.admins.add(admin)
        Membership.objects.get_or_create(user=contributor, community=community)

        article, _ = Article.objects.get_or_create(
            slug="synthetic-reproducible-research",
            defaults={
                "title": "A Synthetic Study of Reproducible Research",
                "abstract": (
                    "A deliberately fictional abstract used to exercise the local "
                    "SciCommons development stack."
                ),
                "authors": [{"name": "Example Researcher"}],
                "submission_type": "Public",
                "submitter": contributor,
                "faqs": [],
            },
        )
        CommunityArticle.objects.get_or_create(
            article=article,
            community=community,
            defaults={"status": CommunityArticle.PUBLISHED},
        )
        Post.objects.get_or_create(
            author=contributor,
            title="Synthetic development discussion",
            defaults={
                "content": (
                    "This fictional post exists only to make local UI and API "
                    "testing repeatable."
                )
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic development data is ready. Login: synthetic-admin / "
                "synthetic-dev-only"
            )
        )
