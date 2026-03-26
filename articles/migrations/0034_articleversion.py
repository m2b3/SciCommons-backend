from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0033_alter_userflag_entity_type_alter_userflag_flag_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArticleVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("version", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=500)),
                ("abstract", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="articles.article",
                    ),
                ),
            ],
            options={
                "ordering": ["-version"],
            },
        ),
    ]
