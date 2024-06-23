import uuid

from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from communities.models import Community
from users.models import User


class Article(models.Model):
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    # Todo: Add Validator
    keywords = models.JSONField(default=list)
    authors = models.JSONField(default=list)
    article_image_url = models.ImageField(
        upload_to="article_images/", null=True, blank=True
    )
    article_pdf_file_url = models.FileField(
        upload_to="article_pdfs/", null=True, blank=True
    )
    submission_type = models.CharField(
        max_length=10, choices=[("Public", "Public"), ("Private", "Private")]
    )
    submitter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="submitted_articles"
    )
    faqs = models.JSONField(default=list)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    # Community to which the article is submitted
    community = models.ForeignKey(
        Community,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    # Status when submitted to a community by the author
    status = models.CharField(
        max_length=10,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    # Status when the article is published by the community
    published = models.BooleanField(default=False)
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


class Review(models.Model):
    article = models.ForeignKey(
        Article, related_name="reviews", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, related_name="reviews", on_delete=models.CASCADE)
    rating = models.IntegerField()
    subject = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} by {self.user.username}"


class ReviewHistory(models.Model):
    review = models.ForeignKey(Review, related_name="history", on_delete=models.CASCADE)
    rating = models.IntegerField()
    subject = models.CharField(max_length=255)
    content = models.TextField()
    edited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"History of {self.review.subject} by {self.review.user.username}"


class Reply(models.Model):
    review = models.ForeignKey(Review, related_name="replies", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="replies", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Reply by {self.user.username} on {self.review.subject}"


# Signals to handle the creation of review history and scheduling deletion
@receiver(pre_save, sender=Review)
def create_review_history(sender, instance, **kwargs):
    if instance.pk:
        original_review = Review.objects.get(pk=instance.pk)
        if (
            original_review.content != instance.content
            or original_review.subject != instance.subject
            or original_review.rating != instance.rating
        ):
            ReviewHistory.objects.create(
                review=original_review,
                rating=original_review.rating,
                subject=original_review.subject,
                content=original_review.content,
            )


# Delete review history when a review is deleted
@receiver(post_delete, sender=Review)
def delete_review_history(sender, instance, **kwargs):
    ReviewHistory.objects.filter(review=instance).delete()


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
