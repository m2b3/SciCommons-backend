from django.db import models


# The `SocialPost` class represents a social media post with a user, body text, optional image, and
# creation timestamp.
class SocialPost(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    body = models.TextField(max_length=2000)
    image = models.FileField(upload_to='social_post_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_post'

    def __str__(self):
        return self.post


# The `SocialPostLike` class represents a like on a social post by a user.
class SocialPostLike(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='likes')

    class Meta:
        db_table = 'social_like'

    def __str__(self):
        return self.value


__all__ = [
    'SocialPost',
    'SocialPostLike',
]
