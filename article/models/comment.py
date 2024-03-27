from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# The CommentBase class is a model in a Python Django application that represents a comment on an
# article, including various fields such as user, article, comment text, rating, confidence, title,
# date, parent comment, tag, comment type, and version.
class CommentBase(models.Model):
    User = models.ForeignKey('user.User', on_delete=models.CASCADE)
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE)
    Comment = models.TextField(max_length=20000)
    rating = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)], null=True, blank=True)
    confidence = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    Title = models.CharField(max_length=200, null=False)
    Comment_date = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey('self', related_name='replies', on_delete=models.CASCADE, null=True, blank=True)
    tag = models.CharField(max_length=255, null=False, default='public')
    comment_type = models.CharField(max_length=255, null=False, default='publiccomment')
    types = models.options = (
        ('review', 'Review'),
        ('decision', 'Decision'),
        ('comment', 'Comment'),
    )
    Type = models.CharField(max_length=10, choices=types, default='comment')
    version = models.ForeignKey('self', related_name='versions', null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        db_table = "comment_base"


# The `LikeBase` class represents a model for storing user likes on comment posts, with a value
# ranging from 0 to 5.
class LikeBase(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    post = models.ForeignKey(CommentBase, on_delete=models.CASCADE, related_name="posts")
    value = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)], null=True, blank=True)

    class Meta:
        db_table = 'like_base'


__all__ = [
    'CommentBase',
    'LikeBase',
]
