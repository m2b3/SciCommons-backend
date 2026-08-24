from django.db import migrations, models
from django.db.models import Count, Min


def remove_duplicate_global_identities(apps, schema_editor):
    """Keep the oldest identity for each article/user pair without a community."""
    AnonymousIdentity = apps.get_model("articles", "AnonymousIdentity")
    database_alias = schema_editor.connection.alias
    duplicate_groups = (
        AnonymousIdentity.objects.using(database_alias)
        .filter(community_id__isnull=True)
        .values("user_id", "article_id")
        .annotate(identity_count=Count("id"), keep_id=Min("id"))
        .filter(identity_count__gt=1)
    )

    for group in duplicate_groups.iterator():
        (
            AnonymousIdentity.objects.using(database_alias)
            .filter(
                community_id__isnull=True,
                user_id=group["user_id"],
                article_id=group["article_id"],
            )
            .exclude(id=group["keep_id"])
            .delete()
        )


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0037_purge_deleted_review_versions"),
    ]

    operations = [
        migrations.RunPython(
            remove_duplicate_global_identities,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="anonymousidentity",
            constraint=models.UniqueConstraint(
                condition=models.Q(("community__isnull", True)),
                fields=("user", "article"),
                name="unique_global_anonymous_identity",
            ),
        ),
    ]
