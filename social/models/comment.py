from django.db import models


# The `SocialPostComment` class represents a comment made by a user on a social post, with fields for
# the user, post, comment text, creation timestamp, and optional parent comment.
class SocialPostComment(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    post = models.ForeignKey('social.SocialPost', on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        db_table = 'social_comment'

    def __str__(self):
        return self.comment


# The `SocialPostCommentLike` class represents a like on a social post comment made by a user.
class SocialPostCommentLike(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    comment = models.ForeignKey(SocialPostComment, on_delete=models.CASCADE, related_name='likes')

    class Meta:
        db_table = 'social_comment_like'

    def __str__(self):
        return self.value


__all__ = [
    'SocialPostComment',
    'SocialPostCommentLike',
]
