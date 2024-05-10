from django.db import models
from django.utils.text import slugify

from articles.models import Article
from users.models import User


class Community(models.Model):
    PUBLIC = "public"
    HIDDEN = "hidden"
    LOCKED = "locked"
    COMMUNITY_TYPES = [(PUBLIC, "Public"), (HIDDEN, "Hidden"), (LOCKED, "Locked")]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=COMMUNITY_TYPES, default=PUBLIC)

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

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)


class Invitation(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

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


class CommunityPost(models.Model):
    community = models.ForeignKey(
        Community, related_name="posts", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cited_article = models.ForeignKey(
        Article, null=True, blank=True, on_delete=models.SET_NULL
    )
    cited_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=200, unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CommunityComment(models.Model):
    post = models.ForeignKey(
        CommunityPost, related_name="comments", on_delete=models.CASCADE
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.author}: {self.content[:50]}..."
