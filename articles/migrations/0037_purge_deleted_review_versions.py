from django.db import migrations


def purge_deleted_review_versions(apps, schema_editor):
    """
    Drop every ReviewVersion belonging to an already soft-deleted review.

    Deleting a review blanks its subject/content, but Review.save() snapshots the previous
    values into ReviewVersion whenever they change - so each delete archived the very text it
    was removing, and ReviewOut handed that history back to any caller. The serializer now
    withholds it and delete_review purges as it goes; this clears the rows written before
    either was true.
    """
    ReviewVersion = apps.get_model("articles", "ReviewVersion")
    ReviewVersion.objects.filter(review__deleted_at__isnull=False).delete()


def noop_reverse(apps, schema_editor):
    """Unrecoverable by design: the whole point is that the content is gone."""


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0036_reconcile_article_identifiers"),
    ]

    operations = [
        migrations.RunPython(purge_deleted_review_versions, noop_reverse),
    ]
