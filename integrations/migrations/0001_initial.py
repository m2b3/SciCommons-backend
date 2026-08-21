import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationAuthCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.CharField(db_index=True, max_length=100)),
                ("code_hash", models.CharField(max_length=64, unique=True)),
                ("code_challenge", models.CharField(max_length=128)),
                ("code_challenge_method", models.CharField(default="S256", max_length=10)),
                ("redirect_uri", models.URLField(max_length=1000)),
                ("state", models.CharField(blank=True, max_length=255, null=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="integration_auth_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="IntegrationDeviceAuth",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.CharField(db_index=True, max_length=100)),
                ("device_code_hash", models.CharField(max_length=64, unique=True)),
                ("user_code_hash", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("consumed", "Consumed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("interval_seconds", models.PositiveSmallIntegerField(default=5)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="integration_device_auths",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="integrationauthcode",
            index=models.Index(fields=["client_id", "expires_at"], name="integration_client__fb2077_idx"),
        ),
        migrations.AddIndex(
            model_name="integrationdeviceauth",
            index=models.Index(fields=["client_id", "status", "expires_at"], name="integration_client__649ed2_idx"),
        ),
    ]
