from django.db import models
from django.utils.text import slugify

from users.models import User


class Community(models.Model):
    PUBLIC = "public"
    HIDDEN = "hidden"
    LOCKED = "locked"
    COMMUNITY_TYPES = [(PUBLIC, "Public"), (HIDDEN, "Hidden"), (LOCKED, "Locked")]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=COMMUNITY_TYPES, default=PUBLIC)
    profile_pic_url = models.FileField(upload_to="community_images/", null=True)
    banner_pic_url = models.FileField(upload_to="community_images/", null=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rules = models.JSONField(default=list)
    about = models.JSONField(default=dict)

    admins = models.ManyToManyField(User, related_name="admin_communities")
    reviewers = models.ManyToManyField(User, related_name="reviewer_communities")
    moderators = models.ManyToManyField(User, related_name="moderator_communities")
    members = models.ManyToManyField(
        User, related_name="member_communities", through="Membership"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def is_member(self, user):
        return self.members.filter(pk=user.pk).exists()

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
    SUBMISSION_STATUS = [
        ("submitted", "Submitted"),
        ("approved", "Approved by Admin"),
        ("under_review", "Under Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("published", "Published"),
    ]
    article = models.ForeignKey("articles.Article", on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=SUBMISSION_STATUS, default="submitted"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)


class ArticleSubmissionAssessment(models.Model):
    community_article = models.ForeignKey(
        CommunityArticle, on_delete=models.CASCADE, related_name="assessments"
    )
    assessor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="article_assessments"
    )
    is_moderator = models.BooleanField(default=False)
    approved = models.BooleanField(null=True)
    comments = models.TextField(blank=True)
    assessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["community_article", "assessor"], name="unique_article_assessor"
            )
        ]
