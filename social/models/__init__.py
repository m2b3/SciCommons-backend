from django.db import models
from .post import SocialPost, SocialPostLike
from .comment import SocialPostComment, SocialPostCommentLike


# The `Follow` class represents a model for tracking user followers and the users they are following.
class Follow(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='following')
    followed_user = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='followers')

    class Meta:
        db_table = 'follow'

    def __str__(self):
        return self.followed_user


def message_media(self, instance, filename):
    if filename:
        return f"message_media/{instance.id}/{filename}"


class Bookmark(models.Model):
    """
    The function `message_media` returns the file path for saving media files associated with a message.

    :param instance: The `instance` parameter refers to the instance of the model that the file is being
    uploaded for. In this case, it could be an instance of the `Bookmark` model or any other model that
    uses the `message_media` function as its `upload_to` parameter
    :param filename: The filename parameter is a string that represents the name of the file being
    uploaded
    :return: The function `message_media` returns a string that represents the file path for a media
    file. The file path is constructed using the `instance.id` and `filename` parameters.
    """
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    post = models.ForeignKey('social.SocialPost', on_delete=models.CASCADE)

    class Meta:
        db_table = 'bookmark'
        unique_together = ['user', 'post']


__all__ = [
    'SocialPost',
    'SocialPostComment',
    'SocialPostLike',
    'SocialPostCommentLike',
    'Follow',
    'Bookmark'
]
