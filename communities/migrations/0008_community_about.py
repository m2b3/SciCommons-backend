# Generated by Django 5.0.7 on 2024-07-24 11:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communities", "0007_remove_community_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="about",
            field=models.JSONField(default=dict),
        ),
    ]
