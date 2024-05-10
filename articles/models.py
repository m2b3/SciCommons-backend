from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# from communities.models import Community
from users.models import User


class Article(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    article_name = models.CharField(max_length=300, unique=True)
    article_file = models.FileField(
        upload_to="articles_file/", null=True, blank=True, name="article_file"
    )
    Public_date = models.DateTimeField(auto_now_add=True, null=True)
    visibility = models.options = (
        ("public", "Public"),
        ("private", "Private"),
    )
    keywords = models.TextField(null=False)
    authorstring = models.TextField(null=False)
    status = models.CharField(max_length=10, choices=visibility, default="public")
    video = models.CharField(max_length=255, blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    license = models.CharField(max_length=255, null=True)
    published_article_file = models.FileField(
        upload_to="published_article_file/",
        null=True,
        blank=True,
        name="published_article_file",
    )
    published = models.CharField(max_length=255, null=True)
    published_date = models.DateTimeField(null=True, blank=True)
    Code = models.CharField(max_length=100, null=True, blank=True)
    Abstract = models.TextField(blank=True, null=True, max_length=5000)
    authors = models.ManyToManyField(
        User, through="Author", related_name="article_authors"
    )
    # community = models.ManyToManyField(Community, through="CommunityMeta")
    views = models.IntegerField(default=0)
    doi = models.CharField(max_length=255, null=True, blank=True)

    # reviewer = models.ManyToManyField(
    #     "app.OfficialReviewer",
    #     through="ArticleReviewer",
    #     related_name="article_reviewers",
    # )
    # moderator = models.ManyToManyField(
    #     "app.Moderator", through="ArticleModerator", related_name="article_moderators"
    # )
    blocked_users = models.ManyToManyField(User, through="ArticleBlockedUser")

    parent_article = models.ForeignKey(
        "self", related_name="versions", null=True, blank=True, on_delete=models.CASCADE
    )

    class Meta:
        db_table = "article"

    def __str__(self) -> str:
        return self.article_name


# The `ArticleReviewer` class represents the relationship between an `Article` and an
# `OfficialReviewer` in a database table called `article_reviewer`.
class ArticleReviewer(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    # officialreviewer = models.ForeignKey(
    #     "app.OfficialReviewer", on_delete=models.CASCADE
    # )

    class Meta:
        db_table = "article_reviewer"

    def __str__(self) -> str:
        return self.article.article_name


# The `ArticleBlockedUser` class represents a model for
# blocking users from accessing an article in a database.
class ArticleBlockedUser(models.Model):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="Article"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = "article_blocked_user"


class Author(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    User = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = "author"
        unique_together = ("article", "User")

    def __str__(self) -> str:
        return self.User.username


class CommentBase(models.Model):
    User = models.ForeignKey(User, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    Comment = models.TextField(max_length=20000)
    rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)], null=True, blank=True
    )
    confidence = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True
    )
    Title = models.CharField(max_length=200, null=False)
    Comment_date = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey(
        "self", related_name="replies", on_delete=models.CASCADE, null=True, blank=True
    )
    tag = models.CharField(max_length=255, null=False, default="public")
    comment_type = models.CharField(max_length=255, null=False, default="publiccomment")
    types = models.options = (
        ("review", "Review"),
        ("decision", "Decision"),
        ("comment", "Comment"),
    )
    Type = models.CharField(max_length=10, choices=types, default="comment")
    version = models.ForeignKey(
        "self", related_name="versions", null=True, blank=True, on_delete=models.CASCADE
    )

    class Meta:
        db_table = "comment_base"


# The `HandlersBase` class is a model that represents a base handler with a user,
# handle name, and article.
class HandlersBase(models.Model):
    User = models.ForeignKey(User, on_delete=models.CASCADE)
    handle_name = models.CharField(max_length=255, null=False, unique=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)

    class Meta:
        db_table = "handler_base"
        unique_together = ["User", "handle_name", "article"]


# The `ArticleMessage` class represents a message sent by a user in a chat
# channel related to an article, with optional media and a timestamp.
class ArticleMessage(models.Model):
    sender = models.ForeignKey(
        User, related_name="sent_article_messages", on_delete=models.CASCADE
    )
    channel = models.CharField(max_length=255)
    article = models.ForeignKey(
        Article, related_name="article_group", on_delete=models.CASCADE
    )
    media = models.FileField(upload_to="message_media/", null=True, blank=True)
    body = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_chat_message"

    def __str__(self) -> str:
        return self.body
