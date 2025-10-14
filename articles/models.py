import random
import time
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from faker import Faker

from myapp import settings
from myapp.utils import generate_identicon
from users.models import HashtagRelation, User


class Article(models.Model):
    title = models.CharField(max_length=500)
    abstract = models.TextField()
    # Todo: Add Validator
    authors = models.JSONField(default=list)

    def get_upload_path(instance, filename):
        # Get file extension
        ext = filename.split(".")[-1]
        # Generate unique filename using article ID and timestamp
        unique_filename = (
            f"{instance.id}_{uuid.uuid4().hex[:8]}_{int(time.time())}.{ext}"
        )
        return f"article_images/{settings.ENVIRONMENT}/{unique_filename}"

    article_image_url = models.ImageField(
        upload_to=get_upload_path, null=True, blank=True
    )
    article_link = models.URLField(null=True, blank=True, unique=True)
    submission_type = models.CharField(
        max_length=10, choices=[("Public", "Public"), ("Private", "Private")]
    )
    submitter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="submitted_articles", db_index=True
    )
    faqs = models.JSONField(default=list)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    hashtags = GenericRelation(HashtagRelation, related_query_name="articles")

    class Meta:
        indexes = [
            models.Index(fields=["submitter", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["submission_type"]),
            models.Index(fields=["submission_type", "created_at"]),
        ]

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
    def get_pdf_upload_path(instance, filename):
        # Get file extension
        ext = filename.split(".")[-1]
        # Generate unique filename using article ID and timestamp
        unique_filename = (
            f"{instance.article.id}_pdf_{uuid.uuid4().hex[:8]}_{int(time.time())}.{ext}"
        )
        return f"article_pdfs/{settings.ENVIRONMENT}/{unique_filename}"

    article = models.ForeignKey(Article, related_name="pdfs", on_delete=models.CASCADE)
    pdf_file_url = models.FileField(
        upload_to=get_pdf_upload_path, null=True, blank=True
    )
    external_url = models.URLField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.article.title} - PDF {self.id}"

    def get_url(self):
        """Return either the local file URL or external URL"""
        if self.pdf_file_url:
            return self.pdf_file_url.url
        return self.external_url


class AnonymousIdentity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    article = models.ForeignKey("Article", on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )
    fake_name = models.CharField(max_length=100)
    identicon = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "article", "community")

    @staticmethod
    def generate_reddit_style_username():
        fake = Faker()

        def cap_word():
            return fake.word().capitalize()

        def low_word():
            return fake.word().lower()

        patterns = [
            lambda: f"{cap_word()}_{cap_word()}_{random.randint(1000, 99999)}",
            lambda: f"{cap_word()}_{cap_word()}{random.randint(10000, 999999):x}",
            lambda: f"{low_word()}_{low_word()}",
            lambda: f"{cap_word()}-{cap_word()}",
            lambda: f"{cap_word()}{uuid.uuid4().hex[:4]}",
            lambda: f"{fake.first_name()}_{''.join(random.choices('aeiouy', k=3))}",
            lambda: f"{cap_word()}{random.choice(['', '_'])}{random.randint(10, 99)}",
            lambda: f"{low_word()}_{cap_word()}{random.choice(['.', '-', '_'])}{uuid.uuid4().hex[:5]}",
            lambda: f"{cap_word()}.{low_word()}{random.randint(100, 999)}{cap_word()}",
            lambda: f"{cap_word()}_{cap_word()}{random.choice(['', str(random.randint(1000, 9999))])}",
        ]
        fake_name = random.choice(patterns)()
        return fake_name

    @classmethod
    def get_or_create_fake_name(cls, user, article, community=None):
        identity, created = cls.objects.get_or_create(
            user=user,
            article=article,
            community=community,
            defaults={
                "fake_name": (fake_name := cls.generate_reddit_style_username()),
                "identicon": generate_identicon(fake_name),
            },
        )
        return identity.fake_name


class Review(models.Model):
    REVIEWER = "reviewer"
    MODERATOR = "moderator"
    PUBLIC = "public"
    REVIEW_TYPES = [
        (REVIEWER, "Reviewer Review"),
        (MODERATOR, "Moderator Decision"),
        (PUBLIC, "Public Review"),
    ]

    article = models.ForeignKey(
        Article, related_name="reviews", on_delete=models.CASCADE, db_index=True
    )
    user = models.ForeignKey(User, related_name="reviews", on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_index=True,
    )
    community_article = models.ForeignKey(
        "communities.CommunityArticle", null=True, blank=True, on_delete=models.CASCADE
    )

    review_type = models.CharField(max_length=10, choices=REVIEW_TYPES, default=PUBLIC)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    subject = models.CharField(max_length=255)
    content = models.TextField()
    is_approved = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reaction = GenericRelation("Reaction", related_query_name="reviews")
    is_pseudonymous = models.BooleanField(default=False, editable=True)

    def __str__(self):
        return (
            f"{self.subject} by {self.user.username} ({self.get_review_type_display()})"
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            old_review = Review.objects.get(pk=self.pk)
            # if either the subject or content has changed, create a new version
            if old_review.subject != self.subject or old_review.content != self.content:
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
        return AnonymousIdentity.get_or_create_fake_name(
            self.user, self.article, self.community
        )

    def delete(self, *args, **kwargs):
        ReviewVersion.objects.filter(review=self).delete()
        super().delete(*args, **kwargs)

    class Meta:
        unique_together = ("article", "user", "community")
        indexes = [
            models.Index(fields=["article", "created_at"]),
            models.Index(fields=["community", "article"]),
            models.Index(fields=["user", "article"]),
            models.Index(fields=["community_article"]),
        ]


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
    is_pseudonymous = models.BooleanField(default=False)

    def __str__(self):
        return f"ReviewComment by {self.author.username}"

    def save(self, *args, **kwargs):
        if self.parent and self.parent.parent and self.parent.parent.parent:
            raise ValueError("Exceeded maximum comment nesting level of 3")
        super().save(*args, **kwargs)

    def get_anonymous_name(self):
        return AnonymousIdentity.get_or_create_fake_name(
            self.author, self.review.article, self.review.community
        )

    class Meta:
        ordering = ["created_at"]


class ReviewCommentRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    review = models.ForeignKey(Review, on_delete=models.CASCADE)
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        unique_together = ("user", "review", "community")


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
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="discussions"
    )
    topic = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reactions = GenericRelation("Reaction")
    is_pseudonymous = models.BooleanField(default=False)

    def __str__(self):
        return f"Discussion: {self.title} (Article: {self.article.title})"

    class Meta:
        ordering = ["-created_at"]

    def get_anonymous_name(self):
        return AnonymousIdentity.get_or_create_fake_name(
            self.author, self.article, self.community
        )


class DiscussionComment(models.Model):
    discussion = models.ForeignKey(
        Discussion, on_delete=models.CASCADE, related_name="discussion_comments"
    )
    community = models.ForeignKey(
        "communities.Community", null=True, blank=True, on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="authored_discussion_comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reactions = GenericRelation("Reaction")
    is_pseudonymous = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return (
            f"Comment by {self.author.username} on Discussion: {self.discussion.title}"
        )

    class Meta:
        ordering = ["created_at"]

    def get_anonymous_name(self):
        return AnonymousIdentity.get_or_create_fake_name(
            self.author, self.discussion.article, self.discussion.community
        )


class DiscussionSubscription(models.Model):
    """
    Model to track user subscriptions to discussions for real-time updates
    Only applies to private/hidden community articles
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="discussion_subscriptions",
        db_index=True,
    )
    community_article = models.ForeignKey(
        "communities.CommunityArticle",
        on_delete=models.CASCADE,
        related_name="discussion_subscribers",
        db_index=True,
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.CASCADE,
        related_name="discussion_subscribers",
        db_index=True,
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="discussion_subscribers",
        db_index=True,
    )
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "community_article", "community")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["community_article", "is_active"]),
            models.Index(fields=["community", "is_active"]),
            models.Index(fields=["article", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.username} subscribed to discussions in {self.community.name} for article {self.article.title}"

    @classmethod
    def create_auto_subscriptions_for_new_article(cls, community_article):
        """
        Create auto-subscriptions when a new article is published to a community
        - All community admins get subscribed
        - Article submitter gets subscribed (if they're a member)

        Optimized with bulk operations and efficient queries
        """
        import logging

        from django.db import transaction

        logger = logging.getLogger(__name__)
        subscriptions_created = []

        # Only work with private/hidden communities
        if community_article.community.type not in ["private", "hidden"]:
            return subscriptions_created

        try:
            with transaction.atomic():
                # Get all potential subscribers in one query
                admin_ids = set(
                    community_article.community.admins.values_list("id", flat=True)
                )

                # Check if submitter is a member
                submitter = community_article.article.submitter
                is_member = community_article.community.members.filter(
                    id=submitter.id
                ).exists()

                user_ids_to_subscribe = admin_ids.copy()
                if is_member:
                    user_ids_to_subscribe.add(submitter.id)

                # Get existing subscriptions to avoid duplicates
                existing_subscriptions = set(
                    cls.objects.filter(
                        community_article=community_article,
                        community=community_article.community,
                        user_id__in=user_ids_to_subscribe,
                    ).values_list("user_id", flat=True)
                )

                # Create subscriptions for users who don't already have them
                new_user_ids = user_ids_to_subscribe - existing_subscriptions

                if new_user_ids:
                    # Bulk create subscriptions
                    new_subscriptions = [
                        cls(
                            user_id=user_id,
                            community_article=community_article,
                            community=community_article.community,
                            article=community_article.article,
                            is_active=True,
                        )
                        for user_id in new_user_ids
                    ]

                    subscriptions_created = cls.objects.bulk_create(new_subscriptions)
                    logger.info(
                        f"Created {len(subscriptions_created)} auto-subscriptions for article '{community_article.article.title}'"
                    )

        except Exception as e:
            logger.error(
                f"Failed to create auto-subscriptions for article '{community_article.article.title}': {e}"
            )
            # Don't re-raise - this shouldn't break the main flow

        return subscriptions_created

    @classmethod
    def create_auto_subscriptions_for_new_admin(cls, user, community):
        """
        Create auto-subscriptions when a user becomes an admin of a community
        Subscribe them to all existing articles in the community

        Optimized with bulk operations and efficient queries
        """
        import logging

        from django.db import transaction

        logger = logging.getLogger(__name__)
        subscriptions_created = []

        # Get all community articles for private/hidden communities only
        if community.type not in ["private", "hidden"]:
            return subscriptions_created

        try:
            with transaction.atomic():
                # Get all published/accepted articles in this community
                community_articles = community.communityarticle_set.filter(
                    status="published"
                ).select_related("article")

                if not community_articles.exists():
                    return subscriptions_created

                # Get existing subscriptions to avoid duplicates
                existing_community_article_ids = set(
                    cls.objects.filter(
                        user=user,
                        community=community,
                        community_article__in=community_articles,
                    ).values_list("community_article_id", flat=True)
                )

                # Create subscriptions for articles that don't already have them
                new_subscriptions = []
                for community_article in community_articles:
                    if community_article.id not in existing_community_article_ids:
                        new_subscriptions.append(
                            cls(
                                user=user,
                                community_article=community_article,
                                community=community,
                                article=community_article.article,
                                is_active=True,
                            )
                        )

                if new_subscriptions:
                    subscriptions_created = cls.objects.bulk_create(new_subscriptions)
                    logger.info(
                        f"Created {len(subscriptions_created)} auto-subscriptions for new admin '{user.username}' in community '{community.name}'"
                    )

        except Exception as e:
            logger.error(
                f"Failed to create auto-subscriptions for new admin '{user.username}': {e}"
            )
            # Don't re-raise - this shouldn't break the main flow

        return subscriptions_created


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
