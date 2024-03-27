from django.db import models


# The `Article` class represents an article model with various fields and properties, including
# article name, file, publication date, visibility, keywords, author information, status, video, link,
# license, published article file, published status, published date, code, abstract, authors,
# community, views, DOI, reviewers, moderators, blocked users, and a parent article.
class Article(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    article_name = models.CharField(max_length=300, unique=True)
    article_file = models.FileField(upload_to='articles_file/', null=True, blank=True, name='article_file')
    Public_date = models.DateTimeField(auto_now_add=True, null=True)
    visibility = models.options = (
        ('public', 'Public'),
        ('private', 'Private'),
    )
    keywords = models.TextField(null=False)
    authorstring = models.TextField(null=False)
    status = models.CharField(max_length=10, choices=visibility, default='public')
    video = models.CharField(max_length=255, blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    license = models.CharField(max_length=255, null=True)
    published_article_file = models.FileField(upload_to='published_article_file/', null=True, blank=True,
                                              name='published_article_file')
    published = models.CharField(max_length=255, null=True)
    published_date = models.DateTimeField(null=True, blank=True)
    Code = models.CharField(max_length=100, null=True, blank=True)
    Abstract = models.TextField(blank=True, null=True, max_length=5000)
    authors = models.ManyToManyField('user.User', through="Author", related_name="article_authors")
    community = models.ManyToManyField('community.Community', through="community.CommunityMeta")
    views = models.IntegerField(default=0)
    doi = models.CharField(max_length=255, null=True, blank=True)

    reviewer = models.ManyToManyField("community.OfficialReviewer", through='ArticleReviewer',
                                      related_name='article_reviewers')
    moderator = models.ManyToManyField("community.Moderator", through='ArticleModerator',
                                       related_name='article_moderators')
    blocked_users = models.ManyToManyField('user.User', through='ArticleBlockedUser')

    parent_article = models.ForeignKey('self', related_name='versions', null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        db_table = 'article'

    def __str__(self) -> str:
        return self.article_name


# The `ArticleReviewer` class represents the relationship between an `Article` and an
# `OfficialReviewer` in a database table called `article_reviewer`.
class ArticleReviewer(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    officialreviewer = models.ForeignKey('community.OfficialReviewer', on_delete=models.CASCADE)

    class Meta:
        db_table = 'article_reviewer'

    def __str__(self) -> str:
        return self.article.article_name


# The `ArticleBlockedUser` class represents a model for blocking users from accessing an article in a
# database.
class ArticleBlockedUser(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='Article')
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)

    class Meta:
        db_table = 'article_blocked_user'


# The `ArticleModerator` class represents the relationship between an `Article` and a `Moderator` in a
# database table called `article_moderator`.
class ArticleModerator(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    moderator = models.ForeignKey('community.Moderator', on_delete=models.CASCADE)

    class Meta:
        db_table = 'article_moderator'

    def __str__(self) -> str:
        return self.article.article_name


# The `Author` class represents the relationship between an `Article` and a `User` in a database, with
# a unique constraint on the combination of `article` and `User`.
class Author(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    User = models.ForeignKey('user.User', on_delete=models.CASCADE)

    class Meta:
        db_table = 'author'
        unique_together = ('article', 'User')

    def __str__(self) -> str:
        return self.User.username


__all__ = [
    'Article',
    'ArticleReviewer',
    'ArticleBlockedUser',
    'ArticleModerator',
    'Author'
]
