from faker import Faker
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from rest_framework import serializers

from article.models import ArticleModerator, ArticleReviewer
from community.models import CommunityMember, Community, Moderator, OfficialReviewer
from user.models import UserActivity

fake = Faker()

'''
CommunityMembers serializer
'''


# The CommunityMemberSerializer class is a serializer that converts CommunityMember model instances
# into JSON representations, including fields for username, email, profile picture URL, and user ID.
class CommunityMemberSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField(read_only=True)
    email = serializers.SerializerMethodField(read_only=True)
    profile_pic_url = serializers.SerializerMethodField(read_only=True)
    user_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CommunityMember
        fields = ['username', 'is_reviewer', 'is_moderator', 'is_admin', 'profile_pic_url', 'user_id', 'email']

    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute
        is expected to have a `username` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username

    def get_email(self, obj):
        """
        The function `get_email` returns the email address of a user object.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute
        is expected to have an `email` attribute
        :return: The email of the user associated with the given object.
        """
        return obj.user.email

    def get_profile_pic_url(self, obj):
        """
        The function `get_profile_pic_url` returns the profile picture URL of a given object's user.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute
        is expected to have a `profile_pic_url` method that returns the URL of the user's profile
        picture
        :return: the profile picture URL of the user object.
        """
        if obj.user.profile_pic_url:
            url = obj.user.profile_pic_url.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'

    def get_user_id(self, obj):
        """
        The function `get_user_id` takes an object as input and returns the ID of the user associated
        with that object.

        :param obj: The `obj` parameter is an object that has a `user` attribute
        :return: The user ID of the given object.
        """
        return obj.user.id


'''
OfficialReviewerSerializer
'''


class OfficialReviewerSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialReviewer
        fields = ['User', 'community']
        depth = 1


'''
ModeratorSerializer
'''


class ModeratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Moderator
        fields = ['user', 'community']
        depth = 1


class PromoteSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True)
    role = serializers.CharField(write_only=True)

    class Meta:
        model = Community
        fields = ['user_id', 'role', 'Community_name', 'members']
        read_only_fields = ['Community_name', 'members']

    def update(self, instance, validated_data):
        """
        The function updates the role of a user in a community and sends an email notification.

        :param instance: The `instance` parameter refers to the instance of the model that is being
        updated. In this case, it seems to be a community object
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. In this case, it is used to get the values of the
        `user_id` and `role` fields
        :return: The `instance` object is being returned.
        """
        user_id = validated_data.get('user_id', None)
        role = validated_data.get('role', None)

        if user_id is None:
            raise serializers.ValidationError(detail={"error": "user id can't be None"})
        member = CommunityMember.objects.filter(community=instance, user_id=user_id).first()

        if member is None:

            if role == "member":
                member = CommunityMember.objects.create(community=instance, user_id=user_id)
                member.is_reviewer = False
                member.is_moderator = False
                member.is_admin = False
                member.save()
                send_mail(
                    "added member",
                    f'You have been added as member to {instance.Community_name}',
                    settings.EMAIL_HOST_USER,
                    [member.user.email],
                    fail_silently=False
                )
                UserActivity.objects.create(
                    user=self.context['request'].user,
                    action=f'you added {member.user.username} to community'
                )
            else:
                raise serializers.ValidationError(detail={"error": "user isn't member of community"})

        try:

            if role is None:
                raise serializers.ValidationError(detail={"error": "role can't be None"})

            elif role == 'reviewer':
                moderator = Moderator.objects.filter(user_id=user_id, community=instance)
                article_moderator = ArticleModerator.objects.filter(moderator_id=moderator.id)
                if article_moderator.exists():
                    raise serializers.ValidationError(
                        detail={"error": "user is moderator of some articles.Can not perform this operation!!!"})
                if moderator.exists():
                    moderator.delete()
                OfficialReviewer.objects.create(User_id=user_id, community=instance, Official_Reviewer_name=fake.name())
                member.is_reviewer = True
                member.is_moderator = False
                member.is_admin = False
                member.save()
                send_mail(
                    "you are Reviewer",
                    f'You have been added as Official Reviewer to {instance.Community_name}',
                    settings.EMAIL_HOST_USER,
                    [member.user.email],
                    fail_silently=False
                )
                UserActivity.objects.create(
                    user=self.context['request'].user,
                    action=f'you added {member.user.username} to {instance.Community_name} as a reviewer'
                )

            elif role == 'moderator':
                reviewer = OfficialReviewer.objects.filter(User_id=user_id, community=instance)
                article_reviewer = ArticleReviewer.objects.filter(officialreviewer_id=reviewer.id)
                if article_reviewer.exists():
                    raise serializers.ValidationError(
                        detail={"error": "user is reviewer of some articles.Can not perform this operation!!!"})
                if reviewer.exists():
                    reviewer.delete()
                Moderator.objects.create(user_id=user_id, community=instance)
                member.is_moderator = True
                member.is_reviewer = False
                member.is_admin = False
                member.save()
                send_mail(
                    "You are a moderator",
                    f'You have been added as a Moderator to {instance.Community_name}',
                    settings.EMAIL_HOST_USER,
                    [member.user.email],
                    fail_silently=False
                )
                UserActivity.objects.create(
                    user=self.context['request'].user,
                    action=f'you added {member.user.username} to {instance.Community_name} as a Moderator'
                )

            elif role == 'admin':
                reviewer = OfficialReviewer.objects.filter(User_id=user_id, community=instance).first()
                if reviewer is not None:
                    reviewer.delete()
                moderator = Moderator.objects.filter(user_id=user_id, community=instance).first()
                if moderator is not None:
                    moderator.delete()
                member.is_moderator = False
                member.is_reviewer = False
                member.is_admin = True
                member.save()
                send_mail(
                    "you are now admin",
                    f'You have been added as Admin to {instance.Community_name}',
                    settings.EMAIL_HOST_USER,
                    [member.user.email],
                    fail_silently=False
                )
                UserActivity.objects.create(
                    user=self.context['request'].user,
                    action=f'you added {member.user.username} to {instance.Community_name} as an Admin'
                )

            elif role == 'member':
                reviewer = OfficialReviewer.objects.filter(User_id=user_id, community=instance)
                if reviewer.exists():
                    reviewer.delete()

                moderator = Moderator.objects.filter(user_id=user_id, community=instance)
                if moderator.exists():
                    moderator.delete()

                member.is_reviewer = False
                member.is_moderator = False
                member.save()
                send_mail(
                    f'you are added to {instance.Community_name}',
                    f'You have been added as member to {instance.Community_name}',
                    settings.EMAIL_HOST_USER,
                    [member.user.email],
                    fail_silently=False
                )
                UserActivity.objects.create(
                    user=self.context['request'].user,
                    action=f'you added {member.user.username} to {instance.Community_name}'
                )

            else:
                raise serializers.ValidationError(
                    detail={"error": " wrong role. role can be 'reviewer','moderator','member'"})

        except IntegrityError as e:
            raise serializers.ValidationError(detail={"error": f'{member.user.username} is already {role}'})

        return instance


__all__ = [
    'OfficialReviewerSerializer',
    'CommunityMemberSerializer',
    'ModeratorSerializer',
    'PromoteSerializer',
]
