"""
Holds the User model and UserManager class.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.timezone import now, timedelta
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifiers
    """

    def create_user(self, username, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with additional fields.
    """

    profile_pic_url = models.FileField(upload_to="profile_images/", null=True)
    pubMed_url = models.CharField(max_length=255, null=True, blank=True)
    google_scholar_url = models.CharField(max_length=255, null=True, blank=True)
    institute = models.CharField(max_length=255, null=True, blank=True)
    email_notify = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)

    objects = UserManager()

    class Meta:
        db_table = "user"

    def __int__(self) -> int:
        return self.id


class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.TextField(null=False)

    class Meta:
        db_table = "user_activity"

    def __str__(self) -> str:
        return f"{self.user}-{self.action}"


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ("posts", "Posts"),
        ("articles", "Articles"),
        ("communities", "Communities"),
        ("users", "Users"),
    ]

    TYPE_CHOICES = [
        ("join_request_sent", "Join Request Sent"),
        ("join_request_received", "Join Request Received"),
        ("article_commented", "Article Commented"),
        ("post_replied", "Post Replied"),
        ("comment_replied", "Comment Replied"),
        ("article_submitted", "Article Submitted"),
    ]

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community", on_delete=models.SET_NULL, null=True, blank=True
    )
    article = models.ForeignKey(
        "articles.Article", on_delete=models.SET_NULL, null=True, blank=True
    )
    # post = models.ForeignKey(
    #     "posts.Post", on_delete=models.SET_NULL, null=True, blank=True
    # )
    # Optional: Add references to other models such as Review or Comment if needed
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message = models.TextField()
    content = models.TextField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.category.title()} - "
            f"{self.get_notification_type_display()} - "
            f"{self.message}"
        )

    def set_expiration(self, days: int):
        self.expires_at = now() + timedelta(days=days)
