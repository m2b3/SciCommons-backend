import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class IntegrationAuthCode(models.Model):
    client_id = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="integration_auth_codes")
    code_hash = models.CharField(max_length=64, unique=True)
    code_challenge = models.CharField(max_length=128)
    code_challenge_method = models.CharField(max_length=10, default="S256")
    redirect_uri = models.URLField(max_length=1000)
    state = models.CharField(max_length=255, null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["client_id", "expires_at"]),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


class IntegrationDeviceAuth(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    CONSUMED = "consumed"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (CONSUMED, "Consumed"),
    ]

    client_id = models.CharField(max_length=100, db_index=True)
    device_code_hash = models.CharField(max_length=64, unique=True)
    user_code_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="integration_device_auths",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    interval_seconds = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["client_id", "status", "expires_at"]),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def approve(self, user) -> None:
        self.user = user
        self.status = self.APPROVED
        self.approved_at = timezone.now()
        self.save(update_fields=["user", "status", "approved_at"])

    def consume(self) -> None:
        self.status = self.CONSUMED
        self.consumed_at = timezone.now()
        self.save(update_fields=["status", "consumed_at"])
