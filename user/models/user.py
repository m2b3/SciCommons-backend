from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import BaseUserManager


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


# The Rank class is a model that represents a user's rank and is associated with a User model.
class Rank(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rank = models.IntegerField(default=0)

    class Meta:
        db_table = 'rank'


__all__ = [
    "User",
    "UserActivity",
    "Rank",
]
