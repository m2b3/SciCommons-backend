from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.text import slugify

from users.models import HashtagRelation, User


class Community(models.Model):
    # PUBLIC = "public"
    # HIDDEN = "hidden"
    # LOCKED = "locked"
    PUBLIC = "public"
    PRIVATE = "private"
    HIDDEN = "hidden"
    COMMUNITY_TYPES = [(PUBLIC, "Public"), (HIDDEN, "Hidden"), (PRIVATE, "Private")]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=COMMUNITY_TYPES, default=PUBLIC)
    profile_pic_url = models.FileField(upload_to="community_images/", null=True)
    banner_pic_url = models.FileField(upload_to="community_images/", null=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rules = models.JSONField(default=list)
    about = models.JSONField(default=dict)
    requires_admin_approval = models.BooleanField(default=False)
    is_pseudonymous = models.BooleanField(default=False)

    admins = models.ManyToManyField(User, related_name="admin_communities")
    reviewers = models.ManyToManyField(User, related_name="reviewer_communities")
    moderators = models.ManyToManyField(User, related_name="moderator_communities")
    members = models.ManyToManyField(
        User, related_name="member_communities", through="Membership"
    )

    hashtags = GenericRelation(HashtagRelation, related_query_name="communities")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def is_member(self, user):
        return self.members.filter(pk=user.pk).exists()

    def is_admin(self, user):
        return self.admins.filter(pk=user.pk).exists()

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)


class Invitation(models.Model):
    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (ACCEPTED, "Accepted"),
        (PENDING, "Pending"),
        (REJECTED, "Rejected"),
    ]
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)

    def __str__(self):
        if self.email:
            return f"Invitation for {self.email} to {self.community.name}"
        elif self.username:
            return f"Invitation for {self.username} to {self.community.name}"
        return f"Invitation to {self.community.name}"


class JoinRequest(models.Model):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (APPROVED, "Approved"),
        (PENDING, "Pending"),
        (REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey("Community", on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    rejection_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} requesting to join {self.community}"


class CommunityArticle(models.Model):
    SUBMITTED = "submitted"
    APPROVED_BY_ADMIN = "approved"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PUBLISHED = "published"

    SUBMISSION_STATUS = [
        (SUBMITTED, "Submitted"),
        (APPROVED_BY_ADMIN, "Approved by Admin"),
        (UNDER_REVIEW, "Under Review"),
        (ACCEPTED, "Accepted"),
        (REJECTED, "Rejected"),
        (PUBLISHED, "Published"),
    ]

    article = models.ForeignKey("articles.Article", on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=SUBMISSION_STATUS, default=SUBMITTED
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    assigned_reviewers = models.ManyToManyField(
        User, related_name="assigned_reviews", blank=True
    )
    assigned_moderator = models.ForeignKey(
        User,
        related_name="assigned_moderations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return (
            f"{self.article.title} in {self.community.name} - "
            f"{self.get_status_display()}"
        )
