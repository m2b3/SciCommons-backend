from django.conf import settings
from django.core.mail import send_mail
from rest_framework import serializers

from community.models import Community, CommunityMember, CommunityMeta
from user.models import Subscribe, UserActivity

'''
Community serializer
'''


# The CommunitySerializer class is a serializer for the Community model, specifying the fields to be
# included in the serialized representation.
class CommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ['id', 'Community_name', 'subtitle', 'description', 'location', 'date', 'github', 'email', 'website',
                  'user', 'members']


# The `CommunitylistSerializer` class is a serializer that serializes the `Community` model and
# includes additional fields for member count, evaluated count, published count, and subscription
# count.
class CommunityListSerializer(serializers.ModelSerializer):
    membercount = serializers.SerializerMethodField()
    evaluatedcount = serializers.SerializerMethodField()
    publishedcount = serializers.SerializerMethodField()
    subscribed = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ['id', 'Community_name', 'subtitle', 'description', 'evaluatedcount', 'subscribed',
                  'membercount', 'publishedcount']

    def get_memberCount(self, obj):
        """
        The function `get_member_count` returns the number of community members for a given object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMember objects that are associated with the given community
        object.
        """
        count = CommunityMember.objects.filter(community=obj.id).count()
        return count

    def get_evaluatedCount(self, obj):
        """
        The function `get_evaluatedCount` returns the count of CommunityMeta objects with a status of
        'accepted', 'rejected', or 'in review' for a given community object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a status of 'accepted', 'rejected', or 'in
        review' and are associated with the given obj.
        """
        count = CommunityMeta.objects.filter(community=obj.id, status__in=['accepted', 'rejected', 'in review']).count()
        return count

    def get_publishedcount(self, obj):
        """
        The function `get_publishedCount` returns the count of accepted CommunityMeta objects associated
        with a given community object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a community ID matching the ID of the
        input object and a status of 'accepted'.
        """
        count = CommunityMeta.objects.filter(community=obj.id, status__in=['accepted']).count()
        return count

    def get_subscribed(self, obj):
        """
        The function `get_subscribed` returns the count of subscribers for a given community object.

        :param obj: The "obj" parameter is an object representing a community
        :return: The number of subscribers for the given community object.
        """
        count = Subscribe.objects.filter(community=obj.id).count()
        return count


# The `CommunityGetSerializer` class is a serializer that serializes the `Community` model and
# includes various fields and methods to determine if a user is a member, reviewer, moderator, or
# admin of the community, as well as the count of members, published content, evaluated content, and
# subscriptions.
class CommunityGetSerializer(serializers.ModelSerializer):
    isMember = serializers.SerializerMethodField()
    isReviewer = serializers.SerializerMethodField()
    isModerator = serializers.SerializerMethodField()
    isAdmin = serializers.SerializerMethodField()
    subscribed = serializers.SerializerMethodField()
    memberCount = serializers.SerializerMethodField()
    publishedCount = serializers.SerializerMethodField()
    evaluatedCount = serializers.SerializerMethodField()
    isSubscribed = serializers.SerializerMethodField()
    admins = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ['id', 'Community_name', 'subtitle', 'description', 'location', 'date', 'github', 'email',
                  'evaluatedCount', 'isSubscribed', 'admins',
                  'website', 'user', 'memberCount', 'publishedCount', 'isMember', 'isReviewer', 'isModerator',
                  'isAdmin', 'subscribed']

    def get_isMember(self, obj):
        """
        The function checks if a user is a member of a community by counting the number of
        CommunityMember objects that match the community ID and the user ID.

        :param obj: The `obj` parameter represents the community object for which we want to check if
        the current user is a member
        :return: the count of CommunityMember objects where the community is equal to `obj.id` and the
        user is equal to `self.context["request"].user`.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        count = CommunityMember.objects.filter(community=obj.id, user=self.context["request"].user).count()
        return count

    def get_isReviewer(self, obj):
        """
        The function `get_isReviewer` checks if a user is a reviewer for a specific community.

        :param obj: The `obj` parameter is an object that represents a community
        :return: the count of CommunityMember objects where the community is equal to `obj.id`, the user
        is equal to `self.context["request"].user`, and `is_reviewer` is True.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        count = CommunityMember.objects.filter(community=obj.id, user=self.context["request"].user,
                                               is_reviewer=True).count()
        return count

    def get_isModerator(self, obj):
        """
        The function `get_isModerator` checks if the authenticated user is a moderator of a specific
        community.

        :param obj: The "obj" parameter represents the community object for which we want to check if
        the current user is a moderator
        :return: the count of CommunityMember objects where the community is equal to `obj.id`, the user
        is equal to `self.context["request"].user`, and `is_moderator` is True.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        count = CommunityMember.objects.filter(community=obj.id, user=self.context["request"].user,
                                               is_moderator=True).count()
        return count

    def get_isAdmin(self, obj):
        """
        The function `get_isAdmin` checks if the authenticated user is an admin of a specific community.

        :param obj: The `obj` parameter is an object representing a community
        :return: the count of CommunityMember objects where the community is equal to `obj.id`, the user
        is equal to `self.context["request"].user`, and `is_admin` is True.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        count = CommunityMember.objects.filter(community=obj.id, user=self.context["request"].user,
                                               is_admin=True).count()
        return count

    def get_memberCount(self, obj):
        """
        The function `get_member_count` returns the number of community members for a given object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMember objects that are associated with the given community
        object.
        """
        count = CommunityMember.objects.filter(community=obj.id).count()
        return count

    def get_evaluatedCount(self, obj):
        """
        The function `get_evaluated_count` returns the count of CommunityMeta objects with a status of
        'accepted', 'rejected', or 'in review' for a given community object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a status of 'accepted', 'rejected', or 'in
        review' and are associated with the given obj.
        """
        count = CommunityMeta.objects.filter(community=obj.id, status__in=['accepted', 'rejected', 'in review']).count()
        return count

    def get_publishedCount(self, obj):
        """
        The function `get_published_count` returns the count of accepted CommunityMeta objects associated
        with a given community object.

        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a community ID matching the ID of the
        input object and a status of 'accepted'.
        """
        count = CommunityMeta.objects.filter(community=obj.id, status__in=['accepted']).count()
        return count

    def get_isSubscribed(self, obj):
        """
        The function checks if a user is subscribed to a community.

        :param obj: The `obj` parameter represents the community object for which we want to check if
        the user is subscribed or not
        :return: a boolean value indicating whether the user is subscribed to a particular community or
        not. If the user is authenticated and has a subscription to the community, it will return True.
        Otherwise, it will return False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        count = Subscribe.objects.filter(user=self.context['request'].user, community=obj.id).count()
        if count > 0:
            return True
        else:
            return False

    def get_admins(self, obj):
        """
        The function "get_admins" returns a list of usernames for community members who are admins in a
        given community.

        :param obj: The "obj" parameter is an instance of the Community model
        :return: a list of usernames of community members who are admins.
        """
        members = CommunityMember.objects.filter(community=obj.id, is_admin=True)
        admins = [member.user.username for member in members]
        return admins

    def get_subscribed(self, obj):
        """
        The function `get_subscribed` returns the count of subscribers for a given community object.

        :param obj: The "obj" parameter is an object representing a community
        :return: The number of subscribers for the given community object.
        """
        count = Subscribe.objects.filter(community=obj.id).count()
        return count


# The `CommunityCreateSerializer` class is a serializer that creates a new community instance, sets
# the community name, adds the user as an admin member, sends an email notification, and logs the
# user's activity.
class CommunityCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ['Community_name', 'subtitle', 'description', 'location', 'date', 'github', 'email', 'website']

    def create(self, validated_data):
        """
        The function creates a new community, sets the community name by replacing spaces with
        underscores, adds the user as an admin member, sends an email notification to the user, logs the
        user's activity, and returns the created instance.

        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new instance of the model. It typically includes the data provided
        by the user in the request payload
        :return: The instance of the created object is being returned.
        """
        community_name = validated_data.pop('Community_name', None)
        validated_data['Community_name'] = community_name.replace(' ', '_')
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.members.add(self.context['request'].user, through_defaults={"is_admin": True})
        instance.save()

        try:
            send_mail(
                "you added new commnity",
                f"You have created a {instance.Community_name} community",
                settings.EMAIL_HOST_USER,
                [self.context['request'].user.email],
                fail_silently=False
            )
        except Exception as e:
            print(e)
            pass

        UserActivity.objects.create(
            user=self.context['request'].user,
            action=f"you have created community {instance.Community_name} "
        )

        return instance


__all__ = [
    "CommunitySerializer",
    "CommunityListSerializer",
    "CommunityGetSerializer",
    "CommunityCreateSerializer",
]
