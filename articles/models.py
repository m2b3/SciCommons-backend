from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from users.models import User


class Article(models.Model):
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    keywords = models.JSONField(default=list)
    authors = models.JSONField(default=list)
    image = models.ImageField(
        upload_to="article_images/", null=True, blank=True
    )  # Handles image uploads
    pdf_file = models.FileField(
        upload_to="article_pdfs/", null=True, blank=True
    )  # Handles PDF uploads
    submission_type = models.CharField(
        max_length=10, choices=[("Public", "Public"), ("Private", "Private")]
    )
    submitter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="submitted_articles"
    )
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
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


@receiver(post_delete, sender=Review)
def handle_review_delete(sender, instance, **kwargs):
    instance.deleted_at = timezone.now()
    instance.save()


@receiver(post_delete, sender=Reply)
def handle_reply_delete(sender, instance, **kwargs):
    instance.deleted_at = timezone.now()
    instance.save()
