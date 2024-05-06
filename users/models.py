"""
Holds the User model and UserManager class.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifiers
    """

    def create_user(self, username, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with additional fields.
    """

    profile_pic_url = models.FileField(upload_to="profile_images/", null=True)
    pubMed_url = models.CharField(max_length=255, null=True, blank=True)
    google_scholar_url = models.CharField(max_length=255, null=True, blank=True)
    institute = models.CharField(max_length=255, null=True, blank=True)
    email_notify = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    activation_token = models.CharField(max_length=255, null=True, blank=True)
    activation_token_created_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    class Meta:
        db_table = "user"

    def __int__(self) -> int:
        return self.id
