"""
Holds the User model and UserManager class.
"""

import time
import uuid
from typing import Literal, Optional, Tuple

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Sum
from django.utils.timezone import now, timedelta
from django.utils.translation import gettext_lazy as _

from myapp import settings


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

    def get_upload_path(instance, filename):
        # Get file extension
        ext = filename.split(".")[-1]
        # Generate unique filename using article ID and timestamp
        unique_filename = (
            f"{instance.id}_user_{uuid.uuid4().hex[:8]}_{int(time.time())}.{ext}"
        )
        return f"profile_images/{settings.ENVIRONMENT}/{unique_filename}"

    profile_pic_url = models.FileField(upload_to=get_upload_path, null=True)
    bio = models.TextField(null=True, blank=True)
    pubMed_url = models.CharField(max_length=255, null=True, blank=True)
    google_scholar_url = models.CharField(max_length=255, null=True, blank=True)
    home_page_url = models.URLField(max_length=255, null=True, blank=True)
    linkedin_url = models.URLField(max_length=255, null=True, blank=True)
    github_url = models.URLField(max_length=255, null=True, blank=True)
    academic_statuses = models.JSONField(
        default=list, blank=True, null=True
    )  # Stores the array of {academic_email, start_year, end_year}

    objects = UserManager()

    class Meta:
        db_table = "user"

    def __int__(self) -> int:
        return self.id


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
        ("article_assigned", "Article Assigned"),
    ]

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community", on_delete=models.SET_NULL, null=True, blank=True
    )
    article = models.ForeignKey(
        "articles.Article", on_delete=models.SET_NULL, null=True, blank=True
    )
    post = models.ForeignKey(
        "posts.Post", on_delete=models.SET_NULL, null=True, blank=True
    )
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


class Hashtag(models.Model):
    name = models.CharField(max_length=25, unique=True)


# Genertic HashTag model
class HashtagRelation(models.Model):
    hashtag = models.ForeignKey(Hashtag, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("hashtag", "content_type", "object_id")

    def __str__(self):
        return f"# {self.hashtag.name}"


class Reputation(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    level = models.CharField(max_length=20, default="Novice")

    # Reputation points for different actions
    SUBMIT_ARTICLE = 10
    REVIEW_ARTICLE = 5
    COMMENT_ON_REVIEW = 2
    CREATE_COMMUNITY = 20
    SUBMIT_TO_COMMUNITY = 5
    REVIEW_COMMUNITY_ARTICLE = 7
    COMMENT_COMMUNITY_ARTICLE = 3
    CREATE_POST = 5
    COMMENT_ON_POST = 2

    # Define the allowed action types
    ActionType = Literal[
        "SUBMIT_ARTICLE",
        "REVIEW_ARTICLE",
        "COMMENT_ON_REVIEW",
        "CREATE_COMMUNITY",
        "SUBMIT_TO_COMMUNITY",
        "REVIEW_COMMUNITY_ARTICLE",
        "COMMENT_COMMUNITY_ARTICLE",
        "CREATE_POST",
        "COMMENT_ON_POST",
    ]

    # Thresholds for different levels
    LEVELS = {
        "Novice": 0,
        "Contributor": 50,
        "Expert": 200,
        "Master": 500,
        "Guru": 1000,
    }

    def add_reputation(self, action: ActionType) -> None:
        """
        Add reputation points based on the action performed
        """
        points = getattr(self, action, 0)
        self.score += points
        self.update_level()
        self.save()

    def update_level(self) -> None:
        """
        Update the user's level based on their current score
        """
        for level, threshold in sorted(
            self.LEVELS.items(), key=lambda x: x[1], reverse=True
        ):
            if self.score >= threshold:
                self.level = level
                break

    @property
    def next_level(self) -> Tuple[Optional[str], int]:
        """
        Return the next level and points needed to reach it
        """
        current_level_index = list(self.LEVELS.keys()).index(self.level)
        if current_level_index < len(self.LEVELS) - 1:
            next_level = list(self.LEVELS.keys())[current_level_index + 1]
            points_needed = self.LEVELS[next_level] - self.score
            return next_level, points_needed
        return None, 0

    @classmethod
    def get_top_users(cls, limit: int = 10):
        """
        Return the top users by reputation score
        """
        return cls.objects.order_by("-score")[:limit]

    @classmethod
    def calculate_community_reputation(cls, community) -> int:
        """
        Calculate the total reputation of a community based on its members
        """
        return (
            cls.objects.filter(user__in=community.members.all()).aggregate(
                Sum("score")
            )["score__sum"]
            or 0
        )

    def __str__(self) -> str:
        return f"{self.user.username} - {self.level} ({self.score} points)"


class Bookmark(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bookmarks", db_index=True
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, db_index=True
    )
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # Unique constraint to prevent duplicate bookmarks
        unique_together = ("user", "content_type", "object_id")
        # Composite indexes for efficient queries
        indexes = [
            # For fetching user's bookmarks filtered by content type (most common query)
            models.Index(
                fields=["user", "content_type", "-created_at"],
                name="bookmark_user_type_created",
            ),
            # For fetching all user's bookmarks sorted by date
            models.Index(
                fields=["user", "-created_at"],
                name="bookmark_user_created",
            ),
            # For checking if a specific item is bookmarked by user
            models.Index(
                fields=["user", "content_type", "object_id"],
                name="bookmark_user_type_obj",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - Bookmark for {self.content_object}"


class UserSetting(models.Model):
    """
    Model to store user-specific configuration settings.
    Uses a flexible key-value structure to store various types of settings.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="settings", db_index=True
    )
    config_name = models.CharField(max_length=100, db_index=True)
    value = models.JSONField()  # Can store boolean, number, string, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "config_name")
        indexes = [
            models.Index(fields=["user", "config_name"], name="user_setting_lookup"),
        ]
        db_table = "user_setting"

    def __str__(self):
        return f"{self.user.username} - {self.config_name}: {self.value}"
