# Reconciliation migration for stacking #168 on top of #167.
#
# #167 (0035) added the identifier fields as globally unique, with canonical_url at URLField's
# default max_length of 200. #168 independently added the same four fields, non-unique, with
# canonical_url at 1000. Only one schema can exist, so this migration lands #168's shape on top
# of #167's:
#
#   * doi / pmid / arxiv_id lose their unique constraint. #168's importer creates a separate
#     article when the only DOI match is another user's private one, which a global unique
#     constraint turns into an IntegrityError (500). Dedup is enforced in the importer instead.
#   * canonical_url widens to 1000 -- publisher landing URLs routinely exceed 200 characters.
#
# The normalisation #167 added to Article.save() (lowercased DOI/arXiv, stripped values) is kept:
# it is what makes importer-side dedup reliable without a database constraint.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0035_article_identifiers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="doi",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="article",
            name="pmid",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="article",
            name="arxiv_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="article",
            name="canonical_url",
            field=models.URLField(blank=True, db_index=True, max_length=1000, null=True),
        ),
    ]
