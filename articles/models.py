import uuid

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from faker import Faker

from users.models import User


class Article(models.Model):
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    # Todo: Add Validator
    authors = models.JSONField(default=list)
    article_image_url = models.ImageField(
        upload_to="article_images/", null=True, blank=True
    )
    submission_type = models.CharField(
        max_length=10, choices=[("Public", "Public"), ("Private", "Private")]
    )
    submitter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="submitted_articles"
    )
    faqs = models.JSONField(default=list)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            original_slug = self.slug
            while Article.objects.filter(slug=self.slug).exists():
                unique_id = uuid.uuid4().hex[:8]  # Generate a short unique ID
                self.slug = f"{original_slug}-{unique_id}"
        super(Article, self).save(*args, **kwargs)

    def __str__(self):
        return self.title


class ArticlePDF(models.Model):
    article = models.ForeignKey(Article, related_name="pdfs", on_delete=models.CASCADE)
    pdf_file_url = models.FileField(upload_to="article_pdfs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.article.title} - PDF {self.id}"


class AnonymousIdentity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    fake_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("user", "article")

    @classmethod
    def get_or_create_fake_name(cls, user, article):
        identity, created = cls.objects.get_or_create(
            user=user, article=article, defaults={"fake_name": Faker().name()}
        )
        return identity.fake_name


class Review(models.Model):
    article = models.ForeignKey(
        Article, related_name="reviews", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, related_name="reviews", on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )

    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    subject = models.CharField(max_length=255)
    content = models.TextField()
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reaction = GenericRelation("Reaction", related_query_name="reviews")

    def __str__(self):
        return f"{self.subject} by {self.user.username}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            old_review = Review.objects.get(pk=self.pk)
            # Todo: Fix versioning logic
            if old_review.content != self.content:
                ReviewVersion.objects.create(
                    review=self,
                    rating=old_review.rating,
                    subject=old_review.subject,
                    content=old_review.content,
                    version=old_review.version,
                )
                self.version = old_review.version + 1
        super().save(*args, **kwargs)

    def get_anonymous_name(self):
        return AnonymousIdentity.get_or_create_fake_name(self.user, self.article)

    def delete(self, *args, **kwargs):
        ReviewVersion.objects.filter(review=self).delete()
        super().delete(*args, **kwargs)

    class Meta:
        unique_together = ("article", "user", "community")


class ReviewVersion(models.Model):
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="versions"
    )
    rating = models.IntegerField()
    subject = models.CharField(max_length=255)
    content = models.TextField()
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Version {self.version} of {self.review.subject}"


class ReviewComment(models.Model):
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="review_comments"
    )
    review_version = models.ForeignKey(
        ReviewVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_comments",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="review_replies",
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="review_comments"
    )
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    reactions = GenericRelation("Reaction", related_query_name="review_comments")

    def __str__(self):
        return f"ReviewComment by {self.user.username}"

    def save(self, *args, **kwargs):
        if self.parent and self.parent.parent and self.parent.parent.parent:
            raise ValueError("Exceeded maximum comment nesting level of 3")
        super().save(*args, **kwargs)

    def get_anonymous_name(self):
        return AnonymousIdentity.get_or_create_fake_name(
            self.author, self.review.article
        )

    class Meta:
        ordering = ["created_at"]


class Reaction(models.Model):
    LIKE = 1
    DISLIKE = -1

    VOTE_CHOICES = ((LIKE, "Like"), (DISLIKE, "Dislike"))

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "content_type", "object_id")

    def __str__(self):
        return (
            f"{self.user.username} - {self.get_vote_display()} on {self.content_object}"
        )


"""
Discussion Threads for Articles
"""


class Discussion(models.Model):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="discussions"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="discussions"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reactions = GenericRelation("Reaction")

    def __str__(self):
        return f"Discussion: {self.title} (Article: {self.article.title})"

    class Meta:
        ordering = ["-created_at"]


class DiscussionComment(models.Model):
    discussion = models.ForeignKey(
        Discussion, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="discussion_comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reactions = GenericRelation("Reaction")

    def __str__(self):
        return (
            f"Comment by {self.author.username} on Discussion: {self.discussion.title}"
        )

    class Meta:
        ordering = ["created_at"]


# # Delete review history when a review is deleted
# @receiver(post_delete, sender=Review)
# def delete_review_history(sender, instance, **kwargs):
#     ReviewHistory.objects.filter(review=instance).delete()


# Todo: Automatically delete reviews and replies after a certain period
# when an article is deleted or review is deleted
# @receiver(post_delete, sender=Review)
# def handle_review_delete(sender, instance, **kwargs):
#     instance.deleted_at = timezone.now()
#     instance.save()


# @receiver(post_delete, sender=Reply)
# def handle_reply_delete(sender, instance, **kwargs):
#     instance.deleted_at = timezone.now()
#     instance.save()
