from django.db import models


# The `Notification` class represents a notification object with fields for user, message, date, read
# status, and a link.
class Notification(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    message = models.CharField(max_length=500)
    date = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'notification'

    def __str__(self):
        return self.message


# The Subscribe class represents a subscription of a user to a community in a database.
class Subscribe(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    community = models.ForeignKey('community.Community', on_delete=models.CASCADE)

    class Meta:
        db_table = 'subscribe'

    def __str__(self):
        return self.user.username


# The `Favourite` class represents a model for storing user's favorite articles in a database.
class Favourite(models.Model):
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)

    class Meta:
        db_table = 'favourite'
        unique_together = ['user', 'article']

    def __str__(self) -> str:
        return self.article.article_name


__all__ = [
    'Notification',
    'Subscribe',
    'Favourite',
]
