from django.db import models
from .article import Article, ArticleModerator, ArticleBlockedUser, ArticleReviewer, Author
from .comment import CommentBase, LikeBase


# The `HandlersBase` class is a model that represents a base handler with a user, handle name, and
# article.
class HandlersBase(models.Model):
    User = models.ForeignKey('user.User', on_delete=models.CASCADE)
    handle_name = models.CharField(max_length=255, null=False, unique=True)
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE)

    class Meta:
        db_table = "handler_base"
        unique_together = ['User', 'handle_name', 'article']


__all__ = [
    'Article',
    'ArticleModerator',
    'ArticleBlockedUser',
    'ArticleReviewer',
    'Author',
    'CommentBase',
    'LikeBase',
    'HandlersBase',
]
