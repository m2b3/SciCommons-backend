# The UserSerializer class is a serializer for the User model that includes various fields and methods
# to retrieve additional information about the user such as rank, followers, following, whether the
# user is being followed, number of posts, and whether the user is the currently authenticated user.
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import serializers

from article.models import Author
from community.models import UnregisteredUser
from social.models import Follow, SocialPost
from user.models import User, Rank, UserActivity


class UserSerializer(serializers.ModelSerializer):
    rank = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    isFollowing = serializers.SerializerMethodField()
    posts = serializers.SerializerMethodField()
    profile_pic_url = serializers.SerializerMethodField()
    personal = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'profile_pic_url', 'first_name', 'last_name', 'email', 'rank', 'followers',
                  'google_scholar', 'pubmed', 'institute', 'following', 'isFollowing', 'posts', 'personal']

    def get_rank(self, obj):
        """
        The function `get_rank` retrieves the rank of a user from the Rank model and returns it as a
        string.

        :param obj: The `obj` parameter is an object that represents a user
        :return: The code is returning the rank of the user as a string.
        """
        try:
            rank = Rank.objects.get(user_id=obj.id)
        except Rank.DoesNotExist:
            rank = Rank.objects.create(rank=0, user_id=obj.id)
            rank.save()
        return f'{int(rank.rank)}'

    def get_followers(self, obj):
        """
        The function "get_followers" returns the number of followers for a given object.

        :param obj: The `obj` parameter is an object representing a user
        :return: The number of followers for the given object.
        """
        followers = Follow.objects.filter(followed_user=obj.id).count()
        return followers

    def get_profile_pic_url(self, obj):
        """
        The function `get_profile_pic_url` returns the profile picture URL of a given object's user.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute
        is expected to have a `profile_pic_url` method that returns the URL of the user's profile
        picture
        :return: the profile picture URL of the user object.
        """
        if obj.profile_pic_url:
            url = obj.profile_pic_url.url.split('?')[0]
            return url

        return 'https://scicommons.s3.amazonaws.com/None'

    def get_following(self, obj):
        """
        The function `get_following` returns the number of users that are being followed by a given
        user.

        :param obj: The "obj" parameter is an object representing a user
        :return: The number of users that the given object is following.
        """
        following = Follow.objects.filter(user=obj.id).count()
        return following

    def get_isFollowing(self, obj):
        """
        The function checks if a user is following another user by checking if there is a record in the
        Follow table with the user and followed_user fields matching the current user and the given user
        object.

        :param obj: The `obj` parameter represents an object that is being checked for follow status. It
        could be a user, a post, or any other object that can be followed by a user
        :return: a boolean value. If the user is authenticated and is following the specified object, it
        will return True. Otherwise, it will return False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if (Follow.objects.filter(user=self.context['request'].user, followed_user=obj.id).count() > 0):
            return True
        else:
            return False

    def get_posts(self, obj):
        """
        The function `get_posts` returns the number of social posts associated with a given user.

        :param obj: The "obj" parameter is an object that represents a user
        :return: The number of SocialPost objects that have a user ID matching the ID of the input
        object.
        """
        posts = SocialPost.objects.filter(user=obj.id).count()
        return posts

    def get_personal(self, obj):
        """
        The function checks if the given object is the same as the user making the request.

        :param obj: The `obj` parameter is an object that represents a user
        :return: a boolean value. If the `obj` parameter is equal to the user object stored in
        `self.context['request'].user`, then it returns `True`. Otherwise, it returns `False`.
        """
        if (obj == self.context['request'].user):
            return True
        else:
            return False


# The `UserCreateSerializer` class is a serializer in Python that creates a new user instance,
# performs validation checks, sets the user's password, saves the user instance, creates a rank for
# the user, sends a welcome email, and returns the created user instance.
class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'profile_pic_url', 'first_name', 'last_name', 'email', 'password']

    def create(self, validated_data):
        """
        The function creates a new user instance, sets their password, saves the instance, checks for
        any unregistered users with the same email and associates them with the new user, creates a rank
        for the user, sends a welcome email, and returns the instance.

        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new user. It typically includes fields such as email, username,
        and any other required fields for creating a user
        :return: The instance of the created user is being returned.
        """
        password = validated_data.pop('password')
        user = self.Meta.model.objects.filter(email=validated_data['email']).first()
        if user:
            raise serializers.ValidationError(
                detail={"error": "User with mail already exists.Please use another email or Login using this mail"})
        user = self.Meta.model.objects.filter(username=validated_data['username']).first()
        if user:
            raise serializers.ValidationError(
                detail={"error": "Username already exists.Please use another username!!!"})

        instance = self.Meta.model.objects.create(**validated_data)
        instance.set_password(password)
        instance.save()
        unregistered = UnregisteredUser.objects.filter(email=instance.email)
        if unregistered is not None:
            for user in unregistered:
                with transaction.atomic():
                    Author.objects.create(User=instance, article=user.article)
                    user.delete()

        rank = Rank.objects.create(rank=0, user_id=instance.id)
        rank.save()

        send_mail(
            "Welcome to Scicommons",
            "Welcome to Scicommons.We hope you will have a great time",
            settings.EMAIL_HOST_USER,
            [instance.email],
            fail_silently=False
        )

        send_mail(
            "Verify your Email",
            f"Please verify your email by clicking on the link below.\n{settings.BASE_URL}/verify?email={instance.email}",
            settings.EMAIL_HOST_USER,
            [instance.email],
            fail_silently=False
        )
        return instance


# The UserUpdateSerializer class is a serializer that represents the User model and includes fields
# for updating user information, including a read-only field for the profile picture URL.
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'profile_pic_url', 'google_scholar', 'pubmed', 'institute']
        read_only_fields = ['id', 'email']


# The UserActivitySerializer class is a serializer for the UserActivity model, specifying the fields
# to be included in the serialized representation.
class UserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = ['id', 'user', 'action']


__all__ = [
    'UserSerializer',
    'UserCreateSerializer',
    'UserUpdateSerializer',
    'UserActivitySerializer',
]
