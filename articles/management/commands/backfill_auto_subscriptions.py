"""
Django management command to backfill auto-subscriptions for existing data

Usage:
    python manage.py backfill_auto_subscriptions
    python manage.py backfill_auto_subscriptions --dry-run  # Preview what would be created
    python manage.py backfill_auto_subscriptions --community-id 123  # Specific community only
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from articles.models import DiscussionSubscription
from communities.models import Community, CommunityArticle


class Command(BaseCommand):
    help = "Backfill auto-subscriptions for existing articles and admins in private/hidden communities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be created without actually creating subscriptions",
        )
        parser.add_argument(
            "--community-id",
            type=int,
            help="Only process this specific community ID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation even if community is public (for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        community_id = options.get("community_id")
        force = options["force"]

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] ' if dry_run else ''}Starting auto-subscription backfill..."
            )
        )

        # Get communities to process
        communities_filter = {}
        if community_id:
            communities_filter["id"] = community_id
        if not force:
            communities_filter["type__in"] = ["private", "hidden"]

        communities = Community.objects.filter(**communities_filter)

        if not communities.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"No communities found with filters: {communities_filter}"
                )
            )
            return

        total_subscriptions = 0

        for community in communities:
            self.stdout.write(
                f"\n--- Processing community: {community.name} ({community.type}) ---"
            )

            # Get published articles in this community
            community_articles = CommunityArticle.objects.filter(
                community=community, status="published"  # Only published articles
            ).select_related("article", "community")

            if not community_articles.exists():
                self.stdout.write(f"  No published articles found in {community.name}")
                continue

            community_subscriptions = 0

            for community_article in community_articles:
                self.stdout.write(
                    f"  Processing article: {community_article.article.title}"
                )

                if dry_run:
                    # Count what would be created
                    admins_count = community.admins.count()
                    submitter_is_member = community.is_member(
                        community_article.article.submitter
                    )
                    potential_subscriptions = admins_count + (
                        1 if submitter_is_member else 0
                    )

                    # Check existing subscriptions
                    existing_count = DiscussionSubscription.objects.filter(
                        community_article=community_article,
                        community=community,
                        is_active=True,
                    ).count()

                    new_subscriptions = max(0, potential_subscriptions - existing_count)

                    self.stdout.write(
                        f"    Would create ~{new_subscriptions} subscriptions "
                        f"(admins: {admins_count}, submitter: {1 if submitter_is_member else 0}, "
                        f"existing: {existing_count})"
                    )
                    community_subscriptions += new_subscriptions

                else:
                    # Actually create subscriptions
                    try:
                        with transaction.atomic():
                            subscriptions_created = DiscussionSubscription.create_auto_subscriptions_for_new_article(
                                community_article
                            )

                            created_count = len(subscriptions_created)
                            self.stdout.write(
                                f"    Created {created_count} subscriptions"
                            )
                            community_subscriptions += created_count

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    Error creating subscriptions for {community_article.article.title}: {e}"
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Total for {community.name}: {community_subscriptions} subscriptions"
                )
            )
            total_subscriptions += community_subscriptions

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Backfill complete! "
                f"Total subscriptions {'would be created' if dry_run else 'created'}: {total_subscriptions}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Run without --dry-run to actually create subscriptions."
                )
            )
