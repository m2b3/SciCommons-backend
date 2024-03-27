from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import serializers

from community.models import CommunityRequests, CommunityMember, Community
from user.models import Rank, UserActivity


# The JoinRequestSerializer class is used to serialize and validate join requests for a community,
# ensuring that the user is not already a member and has not already made a request.
class JoinRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRequests
        fields = ['id', 'user', 'community', 'summary', 'about']
        read_only_fields = ['id', 'user']

    def create(self, validated_data):
        """
        The function creates a new instance of a model with the provided validated data, sets the status
        to 'pending', and associates it with the current user.

        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. It is typically used to create or update an instance
        of the model associated with the serializer
        :return: The instance of the created object is being returned.
        """
        member = CommunityMember.objects.filter(user=self.context['request'].user,
                                                community=validated_data['community']).first()
        if member is not None:
            raise serializers.ValidationError(detail={"error": "you are already member of community"})
        requests = self.Meta.model.objects.filter(status='pending', user=self.context['request'].user).first()
        if requests:
            raise serializers.ValidationError(detail={"error": "you already made request"})
        instance = self.Meta.model.objects.create(**validated_data, status='pending', user=self.context['request'].user)
        instance.save()

        return instance


# The CommunityRequestSerializer class is a serializer for the CommunityRequests model, specifying the
# fields to be included in the serialized representation.
class CommunityRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRequests
        fields = ['id', 'user', 'community', 'summary', 'about', 'status']


# The `CommunityRequestGetSerializer` class is a serializer that converts `CommunityRequests` objects
# into JSON format, including additional fields such as the username, rank, and profile picture URL of
# the user associated with the request.
class CommunityRequestGetSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()
    profile_pic_url = serializers.SerializerMethodField()

    class Meta:
        model = CommunityRequests
        fields = ['id', 'user', 'community', 'summary', 'about', 'status', 'username', 'rank', 'profile_pic_url']

    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute
        is expected to have a `username` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username

    def get_rank(self, obj):
        """
        The function `get_rank` retrieves the rank of a user from the `Rank` model.

        :param obj: The `obj` parameter is an object that represents a user
        :return: The rank of the member.
        """
        member = Rank.objects.filter(user_id=obj.user.id).first()
        return member.rank

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


# The `ApproveRequestSerializer` class is a serializer for the `CommunityRequests` model that allows
# updating of its fields.
class ApproveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRequests
        fields = ['id', 'user', 'community', 'summary', 'about', 'status']

    def update(self, instance, validated_data):
        """
        The function updates the attributes of an instance with the values from the validated data and
        saves the instance.

        :param instance: The `instance` parameter refers to the object that you want to update. It could
        be an instance of a model or any other object that you want to modify
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data that needs to be updated in the `instance`. Each key-value pair in the
        `validated_data` dictionary represents an attribute and its corresponding updated value
        :return: The updated instance is being returned.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


# The `CommunityUpdateSerializer` class is a serializer that handles the updating of a community
# instance, including adding new members, setting attributes, saving the instance, sending an email
# notification, and creating a user activity log.
class CommunityUpdateSerializer(serializers.ModelSerializer):
    members = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )

    class Meta:
        model = Community
        fields = ['id', 'Community_name', 'subtitle', 'description', 'location', 'github', 'email', 'website',
                  'members']
        read_only_fields = ['Community_name', 'id']

    def update(self, instance, validated_data):
        """
        The function updates a community instance with validated data, including adding new members,
        setting attributes, saving the instance, sending an email notification, and creating a user
        activity log.

        :param instance: The "instance" parameter refers to the instance of the Community model that is
        being updated. It represents the specific community object that is being modified
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the instance being updated. It typically includes the updated values for the
        fields of the instance
        :return: The `instance` object is being returned.
        """
        members = validated_data.pop("members", [])
        if members:
            with transaction.atomic():
                for member in members:
                    member = CommunityMember.objects.create(user_id=member, community_id=instance.id)
                    member.save()
                members = [member.user.id for member in CommunityMember.objects.all()]
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.members.set(members)
        instance.save()
        send_mail(
            "you have updated community",
            f'You have updated {instance.Community_name} details',
            settings.EMAIL_HOST_USER,
            [instance.user.email],
            fail_silently=False
        )
        UserActivity.objects.create(
            user=self.context['request'].user,
            action=f'You have updated details in {instance.Community_name}'
        )
        return instance


__all__ = [
    "JoinRequestSerializer",
    "CommunityRequestSerializer",
    "CommunityRequestGetSerializer",
    "ApproveRequestSerializer",
    "CommunityUpdateSerializer",
]
