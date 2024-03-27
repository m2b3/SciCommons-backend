from django.db import models


# The `PersonalMessage` class represents a model for storing personal messages between users,
# including the sender, receiver, message body, media, creation timestamp, and read status.
class PersonalMessage(models.Model):
    sender = models.ForeignKey('user.User', related_name="block_sender_message", on_delete=models.CASCADE)
    channel = models.CharField(max_length=255)
    receiver = models.ForeignKey('user.User', related_name="block_reciever_message", null=True, blank=True,
                                 on_delete=models.CASCADE)
    body = models.TextField(null=True)
    media = models.FileField(upload_to="message_media/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "personalmessage"

    def __str__(self) -> str:
        return self.body


# The `ArticleMessage` class represents a message sent by a user in a chat channel related to an
# article, with optional media and a timestamp.
class ArticleMessage(models.Model):
    sender = models.ForeignKey('user.User', related_name="sent_article_messages", on_delete=models.CASCADE)
    channel = models.CharField(max_length=255)
    article = models.ForeignKey('article.Article', related_name="article_group", on_delete=models.CASCADE)
    media = models.FileField(upload_to="message_media/", null=True, blank=True)
    body = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_chat_message"

    def __str__(self) -> str:
        return self.body


# The `BlockPersonalMessage` class represents a model for blocking personal messages between users in
# a chat system.
class BlockPersonalMessage(models.Model):
    sender = models.ForeignKey('user.User', related_name="sender_message", on_delete=models.CASCADE)
    receiver = models.ForeignKey('user.User', related_name="reciever_message", on_delete=models.CASCADE)

    class Meta:
        db_table = "block_chat_message"

    def __str__(self) -> str:
        return f"{self.sender} - {self.receiver}"


__all__ = [
    "BlockPersonalMessage",
    "PersonalMessage",
    "ArticleMessage",
]
