from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

# Create your models here.

from faker import Faker

fake = Faker()


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """

    def create_user(self, username, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(username, email, password, **extra_fields)


# The `User` class is a subclass of `AbstractUser` with additional fields for profile picture, PubMed
# ID, Google Scholar ID, institute, email notification preference, and email verification status,
# along with methods for retrieving the profile picture URL.
class User(AbstractUser):
    profile_pic_url = models.FileField(upload_to='profile_images/', null=True)
    pubmed = models.CharField(max_length=255, null=True, blank=True)
    google_scholar = models.CharField(max_length=255, null=True, blank=True)
    institute = models.CharField(max_length=255, null=True, blank=True)
    email_notify = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)

    objects = UserManager()

    class Meta:
        db_table = 'user'

    def __int__(self) -> int:
        return self.id


# The `UserActivity` class represents a user's activity with a foreign key to the `User` model and a
# text field for the action.
class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.TextField(null=False)

    class Meta:
        db_table = 'user_activity'

    def __str__(self) -> str:
        return f"{self.user}-{self.action}"


# The `EmailVerify` class is a model in Django that represents an email verification entry, containing
# fields for the user, OTP (one-time password), and an ID.
class EmailVerify(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'email_verify'

    def __str__(self) -> str:
        return str(self.id)


# The `ForgetPassword` class represents a model for storing information about forgotten passwords,
# including the user, a one-time password (OTP), and an ID.
class ForgetPassword(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'forgot_password'

    def __str__(self) -> str:
        return str(self.id)


# The Community class represents a community with various attributes such as title, subtitle,
# description, location, date, github link, email, website, user, and members.
class Community(models.Model):
    title = models.CharField(max_length=300, unique=True, name='Community_name')
    subtitle = models.CharField(max_length=300, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateField(auto_now_add=True, null=True)
    github = models.URLField(max_length=200, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)
    website = models.CharField(max_length=300, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    members = models.ManyToManyField(User, through="CommunityMember", related_name='members')

    class Meta:
        db_table = 'community'

    def __str__(self):
        return self.Community_name


# The `CommunityMember` class represents a member of a community, with fields for the community they
# belong to, the user they are associated with, and their roles within the community.
class CommunityMember(models.Model):
    community = models.ForeignKey("app.Community", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_reviewer = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = 'community_member'
        constraints = [
            models.UniqueConstraint(fields=['community', 'user'], name='unique_admin_per_community'),
            models.UniqueConstraint(fields=['user', 'is_admin'], condition=models.Q(is_admin=True),
                                    name='only_one_community_admin')
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.community}"


# The UnregisteredUser class represents a user who is not registered in the system and is associated
# with an article, with attributes for full name and email.
class UnregisteredUser(models.Model):
    article = models.ForeignKey("article.Article", on_delete=models.CASCADE)
    fullName = models.CharField(max_length=255, null=False)
    email = models.EmailField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'unregistered_user'


# The `OfficialReviewer` class represents an official reviewer in a community, with a user, official
# reviewer name, and community as its attributes.
class OfficialReviewer(models.Model):
    User = models.ForeignKey(User, on_delete=models.CASCADE)
    Official_Reviewer_name = models.CharField(max_length=100)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'officialreviewer'
        unique_together = ['User', 'community']

    def __str__(self) -> str:
        return self.User.username

    'Article',
    'ArticleModerator',
    'ArticleBlockedUser',
    'ArticleReviewer',
    'Author',
    'CommentBase',
    'LikeBase',
    'HandlersBase',


# The Rank class is a model that represents a user's rank and is associated with a User model.
class Rank(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rank = models.IntegerField(default=0)

    class Meta:
        db_table = 'rank'


# The `Notification` class represents a notification object with fields for user, message, date, read
# status, and a link.
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)

    class Meta:
        db_table = 'subscribe'

    def __str__(self):
        return self.user.username


# The `Favourite` class represents a model for storing user's favorite articles in a database.
class Favourite(models.Model):
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'favourite'
        unique_together = ['user', 'article']

    def __str__(self) -> str:
        return self.article.article_name


# The Moderator class represents a moderator in a community, with a foreign key to the Community and
# User models.
class Moderator(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'moderator'
        unique_together = ["user", "community"]

    def __str__(self) -> str:
        return self.user.username


# The `CommunityMeta` class represents the metadata associated with an article in a community,
# including its status.
class CommunityMeta(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE, related_name="article_meta")
    ARTICLE_STATUS = {
        ('submitted', 'submitted'),
        ('in review', 'in review'),
        ('accepted', 'accepted'),
        ('published', 'published'),
        ('rejected by user', 'rejected by user'),
        ('rejected', 'rejected')
    }
    status = models.CharField(max_length=255, choices=ARTICLE_STATUS)

    class Meta:
        db_table = 'community_meta'
        unique_together = ["article", "community"]

    def __str__(self) -> str:
        return f"{self.community} - {self.article}"


# The `CommunityRequests` class represents a model for community requests, including information about
# the request, the user making the request, the community the request is for, and the status of the
# request.
class CommunityRequests(models.Model):
    about = models.CharField(max_length=5000, null=True)
    summary = models.CharField(max_length=5000, null=True)
    user = models.ForeignKey(User, related_name='requests', on_delete=models.CASCADE)
    community = models.ForeignKey(Community, related_name='requests', on_delete=models.CASCADE)
    REQUEST_STATUS = {
        ('pending', 'pending'),
        ('approved', 'approved'),
        ('rejected', 'rejected')
    }
    status = models.CharField(max_length=10, null=False, choices=REQUEST_STATUS)

    class Meta:
        db_table = 'community_request'

    def __str__(self):
        return f"{self.community.Community_name}-{self.user.username}"


# The `SocialPost` class represents a social media post with a user, body text, optional image, and
# creation timestamp.
class SocialPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=2000)
    image = models.FileField(upload_to='social_post_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_post'

    def __str__(self):
        return self.post


# The `SocialPostComment` class represents a comment made by a user on a social post, with fields for
# the user, post, comment text, creation timestamp, and optional parent comment.
class SocialPostComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        db_table = 'social_comment'

    def __str__(self):
        return self.comment


# The `SocialPostLike` class represents a like on a social post by a user.
class SocialPostLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='likes')

    class Meta:
        db_table = 'social_like'

    def __str__(self):
        return self.value


# The `SocialPostCommentLike` class represents a like on a social post comment made by a user.
class SocialPostCommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(SocialPostComment, on_delete=models.CASCADE, related_name='likes')

    class Meta:
        db_table = 'social_comment_like'

    def __str__(self):
        return self.value


# The `Follow` class represents a model for tracking user followers and the users they are following.
class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')

    class Meta:
        db_table = 'follow'

    def __str__(self):
        return self.followed_user


class BookMark(models.Model):
    """
    The function `message_media` returns the file path for saving media files associated with a message.
    
    :param instance: The `instance` parameter refers to the instance of the model that the file is being
    uploaded for. In this case, it could be an instance of the `BookMark` model or any other model that
    uses the `message_media` function as its `upload_to` parameter
    :param filename: The filename parameter is a string that represents the name of the file being
    uploaded
    :return: The function `message_media` returns a string that represents the file path for a media
    file. The file path is constructed using the `instance.id` and `filename` parameters.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE)

    class Meta:
        db_table = 'bookmark'
        unique_together = ['user', 'post']


def message_media(self, instance, filename):
    if filename:
        return f"message_media/{instance.id}/{filename}"


# The `BlockPersonalMessage` class represents a model for blocking personal messages between users in
# a chat system.
class BlockPersonalMessage(models.Model):
    sender = models.ForeignKey(User, related_name="sender_message", on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name="reciever_message", on_delete=models.CASCADE)

    class Meta:
        db_table = "block_chat_message"

    def __str__(self) -> str:
        return f"{self.sender} - {self.receiver}"


# The `PersonalMessage` class represents a model for storing personal messages between users,
# including the sender, receiver, message body, media, creation timestamp, and read status.
class PersonalMessage(models.Model):
    sender = models.ForeignKey(User, related_name="block_sender_message", on_delete=models.CASCADE)
    channel = models.CharField(max_length=255)
    receiver = models.ForeignKey(User, related_name="block_reciever_message", null=True, blank=True,
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
    sender = models.ForeignKey(User, related_name="sent_article_messages", on_delete=models.CASCADE)
    channel = models.CharField(max_length=255)
    article = models.ForeignKey('article.Article', related_name="article_group", on_delete=models.CASCADE)
    media = models.FileField(upload_to="message_media/", null=True, blank=True)
    body = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_chat_message"

    def __str__(self) -> str:
        return self.body
