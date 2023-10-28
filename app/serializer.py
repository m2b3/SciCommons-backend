import datetime
import random
import uuid
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import IntegrityError, transaction
from faker import Faker
from django.core.mail import send_mail
from django.db.models import Avg, Sum , Q
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from decouple import config
from dj_database_url import parse

import json



fake = Faker()

from app.models import *

'''
user serializers
'''
# The UserSerializer class is a serializer for the User model that includes various fields and methods
# to retrieve additional information about the user such as rank, followers, following, whether the
# user is being followed, number of posts, and whether the user is the currently authenticated user.
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
        fields = ['id', 'username','profile_pic_url', 'first_name', 'last_name', 'email', 'rank', 'followers',
                  'google_scholar','pubmed','institute', 'following', 'isFollowing', 'posts', 'personal']
        
    def get_rank(self, obj):
        """
        The function `get_rank` retrieves the rank of a user from the Rank model and returns it as a
        string.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: The code is returning the rank of the user as a string.
        """
        rank = Rank.objects.get(user_id=obj.id)
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
    
    def get_personal(self,obj):
        """
        The function checks if the given object is the same as the user making the request.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: a boolean value. If the `obj` parameter is equal to the user object stored in
        `self.context['request'].user`, then it returns `True`. Otherwise, it returns `False`.
        """
        if(obj == self.context['request'].user):
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
            raise serializers.ValidationError(detail={"error": "User with mail already exists.Please use another email or Login using this mail"})
        user = self.Meta.model.objects.filter(username=validated_data['username']).first()
        if user:
            raise serializers.ValidationError(detail={"error":"Username already exists.Please use another username!!!"})
        
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
        send_mail("Welcome to Scicommons", "Welcome to Scicommons.We hope you will have a great time", settings.EMAIL_HOST_USER, [instance.email], fail_silently=False)

        return instance
    
# The UserUpdateSerializer class is a serializer that represents the User model and includes fields
# for updating user information, including a read-only field for the profile picture URL.
class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'profile_pic_url', 'google_scholar', 'pubmed', 'institute']
        read_only_fields = ['id', 'email']

        
# The `LoginSerializer` class is a serializer used for validating and authenticating user login
# credentials, and generating access and refresh tokens.
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, read_only=True)
    password = serializers.CharField(max_length=128, write_only=True)
    access = serializers.CharField(max_length=255, read_only=True)
    refresh = serializers.CharField(max_length=255, read_only=True)
    email = serializers.CharField(max_length=255, read_only=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email','id']


    def validate(self, data):
        """
        The `validate` function checks the validity of user credentials (username, email, and password)
        and returns a token for authentication if the credentials are valid.
        
        :param data: The `data` parameter is the data that needs to be validated. It is a dictionary
        containing the values for the fields `username`, `email`, and `password`
        :return: a dictionary containing the access token and refresh token.
        """
        request = self.context.get('request')
        username = request.data.get("username", None)
        email = request.data.get("email",None)
        password = request.data.get("password", None)
        if username is None and email is None:
            raise serializers.ValidationError(detail={"error":"Username or email must be entered"})

        if username is None and email is not None:
            member = User.objects.filter(email=email).first()
            if member is None:
                raise serializers.ValidationError(detail={"error":"Enter a valid email address"})
            username = member.username

        member = User.objects.filter(username=username).first()
        if member is None:
            raise serializers.ValidationError(
                detail={"error":"Account does not exist. \nPlease try registering to scicommons first"}
            )
        elif member.email_verified == False:
            raise serializers.ValidationError(detail={"error": "Please Verify your Email!!!"})
        
        user = authenticate(username=username, password=password)

        if user and not user.is_active:
            raise serializers.ValidationError(
                detail={"error":"Account has been deactivated. \n Please contact your company's admin to restore your account"}
            )

        if not user:
            raise serializers.ValidationError(detail={"error":"Username or Password is wrong"})

        refresh = RefreshToken.for_user(user)
        data = {"access": str(refresh.access_token), "refresh": str(refresh)}

        UserActivity.objects.create(user=user, action=f"you Logged in at {datetime.datetime.now()}")

        return data

# The UserActivitySerializer class is a serializer for the UserActivity model, specifying the fields
# to be included in the serialized representation.
class UserActivitySerializer(serializers.ModelSerializer):
    
    class Meta:
        model = UserActivity
        fields = ['id','user','action']

# The `ForgotPasswordSerializer` class is a serializer for handling forgot password requests, with an
# email field.
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    class Meta:
        fields = ["email"]
        
# The class `ResetPasswordSerializer` is a serializer class in Python that is used for resetting a
# password and includes fields for OTP, password, and password confirmation.
class ResetPasswordSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    password = serializers.CharField()
    password2 = serializers.CharField()
    
    class Meta:
        fields = ['otp', 'password', 'password2']

# The above class is a serializer class in Python used for verifying OTP and email.
class VerifySerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    email = serializers.CharField()

    class Meta:
        fields = ['otp', 'email']
        

'''
community serializer
'''
# The CommunitySerializer class is a serializer for the Community model, specifying the fields to be
# included in the serialized representation.
class CommunitySerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Community
        fields = ['id', 'Community_name', 'subtitle', 'description', 'location', 'date', 'github', 'email', 'website', 'user', 'members']

# The `CommunitylistSerializer` class is a serializer that serializes the `Community` model and
# includes additional fields for member count, evaluated count, published count, and subscription
# count.
class CommunitylistSerializer(serializers.ModelSerializer):
    membercount = serializers.SerializerMethodField()
    evaluatedcount = serializers.SerializerMethodField()
    publishedcount = serializers.SerializerMethodField()
    subscribed = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = ['id', 'Community_name','subtitle', 'description', 'evaluatedcount', 'subscribed',
                    'membercount','publishedcount']
    
    def get_membercount(self, obj):
        """
        The function `get_membercount` returns the number of community members for a given object.
        
        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMember objects that are associated with the given community
        object.
        """
        count = CommunityMember.objects.filter(community=obj.id).count()
        return count
    
    def get_evaluatedcount(self, obj):
        """
        The function `get_evaluatedcount` returns the count of CommunityMeta objects with a status of
        'accepted', 'rejected', or 'in review' for a given community object.
        
        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a status of 'accepted', 'rejected', or 'in
        review' and are associated with the given obj.
        """
        count = CommunityMeta.objects.filter(community=obj.id,status__in=['accepted', 'rejected', 'in review']).count()
        return count 
    
    def get_publishedcount(self, obj):
        """
        The function `get_publishedcount` returns the count of accepted CommunityMeta objects associated
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
    membercount = serializers.SerializerMethodField()
    publishedcount = serializers.SerializerMethodField()
    evaluatedcount = serializers.SerializerMethodField()
    isSubscribed = serializers.SerializerMethodField()
    admins = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = ['id', 'Community_name','subtitle', 'description','location','date','github','email', 'evaluatedcount', 'isSubscribed', 'admins',
                    'website','user','membercount','publishedcount','isMember','isReviewer', 'isModerator', 'isAdmin','subscribed']
    

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
        count = CommunityMember.objects.filter(community=obj.id,user = self.context["request"].user).count()
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
        count = CommunityMember.objects.filter(community=obj.id,user = self.context["request"].user, is_reviewer=True).count()
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
        count = CommunityMember.objects.filter(community=obj.id,user = self.context["request"].user, is_moderator=True).count()
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
        count = CommunityMember.objects.filter(community=obj.id,user = self.context["request"].user, is_admin=True).count()
        return count
    
    def get_membercount(self, obj):
        """
        The function `get_membercount` returns the number of community members for a given object.
        
        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMember objects that are associated with the given community
        object.
        """
        count = CommunityMember.objects.filter(community=obj.id).count()
        return count
    
    def get_evaluatedcount(self, obj):
        """
        The function `get_evaluatedcount` returns the count of CommunityMeta objects with a status of
        'accepted', 'rejected', or 'in review' for a given community object.
        
        :param obj: The "obj" parameter is an object that represents a community
        :return: the count of CommunityMeta objects that have a status of 'accepted', 'rejected', or 'in
        review' and are associated with the given obj.
        """
        count = CommunityMeta.objects.filter(community=obj.id,status__in=['accepted', 'rejected', 'in review']).count()
        return count 
    
    def get_publishedcount(self, obj):
        """
        The function `get_publishedcount` returns the count of accepted CommunityMeta objects associated
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
        count = Subscribe.objects.filter(user=self.context['request'].user,community=obj.id).count()
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
        validated_data['Community_name'] = community_name.replace(' ','_')
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.members.add(self.context['request'].user, through_defaults={"is_admin":True})
        instance.save()
        
        send_mail("you added new commnity", f"You have created a {instance.Community_name} community", settings.EMAIL_HOST_USER, [self.context['request'].user.email], fail_silently=False)        
        UserActivity.objects.create(user=self.context['request'].user, action=f"you have created community {instance.Community_name} ")

        return instance


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
        member = CommunityMember.objects.filter(user=self.context['request'].user, community=validated_data['community']).first()
        if member is not None:
            raise serializers.ValidationError(detail={"error":"you are already member of community"})
        requests = self.Meta.model.objects.filter(status='pending', user=self.context['request'].user).first()
        if requests:
            raise serializers.ValidationError(detail={"error":"you already made request"})  
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


# The `ApproverequestSerializer` class is a serializer for the `CommunityRequests` model that allows
# updating of its fields.
class ApproverequestSerializer(serializers.ModelSerializer):

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
        fields = ['id','Community_name','subtitle', 'description', 'location', 'github', 'email', 'website', 'members']
        read_only_fields = ['Community_name','id']

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
        send_mail("you have updated community" , f'You have updated {instance.Community_name} details', settings.EMAIL_HOST_USER,[instance.user.email], fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user, action=f'you have updated deatils in {instance.Community_name}')
        return instance


# The SubscribeSerializer class is a serializer for the Subscribe model, with fields for id, user, and
# community, and the id field is read-only.
class SubscribeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Subscribe
        fields = ['id', 'user', 'community']
        read_only_fields = ['id']

        

class PromoteSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only = True)
    role = serializers.CharField(write_only = True)
    
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
                send_mail("added member" , f'You have been added as member to {instance.Community_name}', settings.EMAIL_HOST_USER , [member.user.email], fail_silently=False)
                UserActivity.objects.create(user=self.context['request'].user, action=f'you added {member.user.username} to community')
            else:
                raise serializers.ValidationError(detail={"error": "user isn't member of community"})
        
        try:
        
            if role is None:
                raise serializers.ValidationError(detail={"error": "role can't be None"})
            
            elif role == 'reviewer':
                moderator = Moderator.objects.filter(user_id=user_id, community=instance)
                article_moderator = ArticleModerator.objects.filter(moderator_id=moderator.id)
                if article_moderator.exists():
                    raise serializers.ValidationError(detail={"error": "user is moderator of some articles.Can not perform this operation!!!"})
                if moderator.exists():
                    moderator.delete()
                OfficialReviewer.objects.create(User_id=user_id, community=instance, Official_Reviewer_name=fake.name())
                member.is_reviewer = True
                member.is_moderator = False
                member.is_admin = False
                member.save()
                send_mail("you are Reviewer", f'You have been added as Official Reviewer to {instance.Community_name}', settings.EMAIL_HOST_USER , [member.user.email], fail_silently=False)
                UserActivity.objects.create(user=self.context['request'].user, action=f'you added {member.user.username} to {instance.Community_name} as reviewer')
                
            elif role == 'moderator':
                reviewer = OfficialReviewer.objects.filter(User_id=user_id, community=instance)
                article_reviewer = ArticleReviewer.objects.filter(officialreviewer_id=reviewer.id)
                if article_reviewer.exists():
                    raise serializers.ValidationError(detail={"error": "user is reviewer of some articles.Can not perform this operation!!!"})
                if reviewer.exists():
                    reviewer.delete()
                Moderator.objects.create(user_id=user_id, community=instance)
                member.is_moderator = True
                member.is_reviewer = False
                member.is_admin = False
                member.save()
                send_mail(" you are moderator", f'You have been added as Moderator to {instance.Community_name}', settings.EMAIL_HOST_USER , [member.user.email], fail_silently=False)
                UserActivity.objects.create(user=self.context['request'].user, action=f'you added {member.user.username} to {instance.Community_name} as moderator')
                
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
                send_mail("you are now admin", f'You have been added as Admin to {instance.Community_name}', settings.EMAIL_HOST_USER , [member.user.email], fail_silently=False)
                UserActivity.objects.create(user=self.context['request'].user, action=f'you added {member.user.username} to {instance.Community_name} as admin')
                                
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
                send_mail(f'you are added to {instance.Community_name}',f'You have been added as member to {instance.Community_name}', settings.EMAIL_HOST_USER , [member.user.email], fail_silently=False)
                UserActivity.objects.create(user=self.context['request'].user, action=f'you added {member.user.username} to {instance.Community_name}')
                    
            else:
                raise serializers.ValidationError(detail={"error": " wrong role. role can be 'reviewer','moderator','member'"}) 
            
        except IntegrityError as e:
            raise serializers.ValidationError(detail={"error": f'{member.user.username} is already {role}'}) 
        
        return instance
        
        
'''
article serializers
'''
# The `ArticleSerializer` class is a serializer for the `Article` model that includes a `rating` field
# calculated based on the average rating of related `CommentBase` objects.
class ArticleSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField()
    class Meta:
        model = Article
        fields = ['id', 'article_name', 'Public_date', 'rating', 'authors']
    
    def get_rating(self, obj):
        """
        The function `get_rating` calculates the average rating of comments with the type 'review' for a
        given article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: the average rating of comments that have a type of 'review' for a given article object.
        """
        rating = CommentBase.objects.filter(article_id=obj.id,Type='review').aggregate(Avg('rating'))['rating__avg']
        return rating


# The class ArticlePublishSelectionSerializer is a serializer class in Python that defines the fields
# to be included when serializing an Article model object.
class ArticlePublishSelectionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Article
        fields = ['id', 'published','status']

# The above class is a serializer for the Article model that includes fields for the license,
# published article file, published date, and DOI.
class ArticlePostPublishSerializer(serializers.ModelSerializer):

    class Meta:
        model = Article
        fields = ["license","published_article_file", "published_date", "doi"]


# The `ArticlelistSerializer` class is a serializer that serializes the `Article` model and includes
# additional fields such as rating, isFavourite, favourites, authors, and unregistered_authors.
class ArticlelistSerializer(serializers.ModelSerializer):

    rating = serializers.SerializerMethodField()
    isFavourite = serializers.SerializerMethodField()
    favourites = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    unregistered_authors = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ['id', 'article_name', 'Public_date','views', 'authors','rating', 'isFavourite', 'keywords', 'favourites', 'unregistered_authors']
    
    def get_rating(self, obj):
        """
        The function `get_rating` calculates the average rating of comments with the type 'review' for a
        given article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: the average rating of comments that have a type of 'review' for a given article object.
        """
        rating = CommentBase.objects.filter(article_id=obj.id,Type='review').aggregate(Avg('rating'))['rating__avg']
        return rating
    
    def get_favourites(self, obj):
        """
        The function `get_favourites` returns the count of favourites for a given article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: The number of favourites for the given article object.
        """
        favourites = Favourite.objects.filter(article_id=obj.id).count()
        return favourites
    
    def get_isFavourite(self, obj):
        """
        The function `get_isFavourite` checks if a user is authenticated and if they have favorited a
        specific article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: a boolean value. It returns True if the user is authenticated and the article is in the
        user's favorites list, and False otherwise.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        elif (Favourite.objects.filter(article=obj.id,user=self.context['request'].user).count() > 0):
            return True 
        else:
            return False
    
    def get_authors(self, obj):
        """
        The function "get_authors" returns a list of usernames for all the authors associated with a
        given object.
        
        :param obj: The `obj` parameter is an object that has a many-to-many relationship with the
        `authors` field
        :return: a list of usernames of the authors associated with the given object.
        """
        authors = [user.username for user in obj.authors.all()]
        return authors
    
    def get_unregistered_authors(self,obj):
        """
        The function "get_unregistered_authors" returns a list of dictionaries containing the full name
        and email of unregistered users associated with a given article.
        
        :param obj: The "obj" parameter is an instance of an article object
        :return: a list of dictionaries, where each dictionary represents an unregistered author
        associated with the given article object. Each dictionary contains the full name and email of
        the author.
        """
        unregistered = UnregisteredUser.objects.filter(article=obj.id)
        authors = [{'fullName':user.fullName, 'email':user.email} for user in unregistered]
        return authors

        

class ArticleGetSerializer(serializers.ModelSerializer):
    versions = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    isArticleReviewer = serializers.SerializerMethodField()           
    isArticleModerator = serializers.SerializerMethodField()
    isFavourite = serializers.SerializerMethodField()
    isAuthor = serializers.SerializerMethodField()
    userrating = serializers.SerializerMethodField()
    commentcount = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    unregistered_authors = serializers.SerializerMethodField()
    article_file = serializers.SerializerMethodField()
    favourites = serializers.SerializerMethodField()
    published_article_file = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ['id', 'article_name', 'article_file', 'Public_date', 'Code', 'Abstract','views','video','doi', 'published_article_file',
                    'link', 'authors','rating','versions','isArticleReviewer','isArticleModerator','isAuthor','status',
                    'isFavourite', 'userrating','commentcount', 'favourites','license','published_date', 'published','unregistered_authors' ]
    
    def get_versions(self, obj):
        """
        The function `get_versions` returns serialized data of child articles based on whether the given
        object has a parent article or not.
        
        :param obj: The `obj` parameter is an instance of the `Article` model
        :return: serialized child articles. If the given object does not have a parent article, it
        returns the serialized versions of the object. If the object has a parent article, it returns
        the serialized child articles that have the same parent article as the given object.
        """
        
        if not obj.parent_article:
            serialized_child_articles  = ArticleGetSerializer(obj.versions.all(), many=True)
            return serialized_child_articles.data
        
        else:
            child_articles = Article.objects.exclude(id=obj.id).filter(parent_article=obj.parent_article)
            serialized_child_articles  = ArticleGetSerializer(child_articles, many=True)
            return serialized_child_articles.data
    
    def get_article_file(self, obj):
        if obj.article_file:
            url = obj.article_file.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_published_article_file(self,obj):
        if obj.published_article_file:
            url = obj.published_article_file.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_commentcount(self, obj):
        """
        The function `get_commentcount` returns the count of top-level comments for a given article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: the count of comments that meet the specified criteria.
        """
        count = CommentBase.objects.filter(article_id=obj.id,parent_comment=None,version=None).count()
        return count
    
    def get_favourites(self, obj):
        """
        The function `get_favourites` returns the count of favourites for a given article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: The number of favourites for the given article object.
        """
        favourites = Favourite.objects.filter(article_id=obj.id).count()
        return favourites
    
    def get_rating(self, obj):
        """
        The function `get_rating` calculates the average rating of comments with the type 'review' for a
        given article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: the average rating of all the review comments associated with the given object.
        """
        rating = CommentBase.objects.filter(article_id=obj.id,Type='review').aggregate(Avg('rating'))['rating__avg']
        return rating

    def get_isArticleReviewer(self, obj):
        """
        The function checks if a user is an article reviewer for a given article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: a boolean value. It returns True if the conditions specified in the function are met,
        and False otherwise.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if (ArticleReviewer.objects.filter(article=obj.id,officialreviewer__User_id=self.context['request'].user).count()>0):
            return True
        else:
            return False
    
    def get_isArticleModerator(self, obj):
        """
        The function checks if the authenticated user is a moderator for a specific article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: a boolean value. It returns True if the user is authenticated and is a moderator for
        the given article, and False otherwise.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if(ArticleModerator.objects.filter(article=obj.id,moderator__user_id=self.context['request'].user).count()>0):
            return True
        else:
            return False
    
    def get_isAuthor(self, obj):
        """
        The function checks if the authenticated user is the author of a given article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: a boolean value. It returns True if the user is authenticated and is the author of the
        article, and False otherwise.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if(Author.objects.filter(article=obj.id,User=self.context['request'].user).count()>0):
            return True
        else:
            return False
    
    def get_isFavourite(self, obj):
        """
        The function `get_isFavourite` checks if a user has favorited an article.
        
        :param obj: The "obj" parameter is an object that represents an article
        :return: a boolean value. It returns True if the user is authenticated and the given article is
        in the user's favorites list. Otherwise, it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if (Favourite.objects.filter(article=obj.id,user=self.context['request'].user).count() > 0):
            return True 
        else:
            return False
    
    def get_userrating(self, obj):
        """
        The function "get_userrating" returns the rating given by the authenticated user for a specific
        article, or 0 if the user is not authenticated or has not given a rating.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: the rating value of a user's review for a specific article. If the user is not
        authenticated, it returns 0. If the user is authenticated but has not provided a rating for the
        article, it also returns 0. Otherwise, it returns the rating value as a string.
        """
        if self.context['request'].user.is_authenticated is False:
            return 0
        rating = CommentBase.objects.filter(article_id=obj.id,Type='review',User=self.context['request'].user).first()
        if rating is None:
            return 0
        return f'{rating.rating}'
    
    def get_authors(self, obj):
        """
        The function "get_authors" returns a list of usernames for all the authors associated with a
        given object.
        
        :param obj: The `obj` parameter is an object that has a many-to-many relationship with the
        `authors` field
        :return: a list of usernames of the authors associated with the given object.
        """
        authors = [user.username for user in obj.authors.all()]
        return authors

    def get_unregistered_authors(self,obj):
        """
        The function "get_unregistered_authors" returns a list of dictionaries containing the full name
        and email of unregistered users associated with a given article.
        
        :param obj: The "obj" parameter is an object that represents an article. It is used to filter
        the UnregisteredUser objects based on the article's ID
        :return: a list of dictionaries, where each dictionary represents an unregistered author
        associated with the given article object. Each dictionary contains the full name and email of
        the author.
        """
        unregistered = UnregisteredUser.objects.filter(article=obj.id)
        authors = [{'fullName':user.fullName} for user in unregistered]
        return authors

# The `ArticleBlockUserSerializer` class is a serializer that allows users to be added to the
# `blocked_users` field of an `Article` instance.
class ArticleBlockUserSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    class Meta:
        model = Article
        fields = ["id", "article_name", "blocked_users", 'user_id']
        read_only_fields = ["id", "article_name", "blocked_users"]

    def update(self, instance, validated_data):
        """
        The function updates an instance by adding a user to the blocked_users field and saving the
        instance.
        
        :param instance: The instance parameter refers to the object that you want to update. In this
        case, it seems like it is an instance of a model
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. It is typically used in the `update` method of a
        serializer to update the instance with the new data. In this case, it is expected to contain a
        key "user" which represents the user to
        :return: The updated instance is being returned.
        """
        instance.blocked_users.add(validated_data["user"])
        instance.save()

        return instance
        

# The `ArticleViewsSerializer` class is a serializer for the `Article` model that includes the `views`
# field.
class ArticleViewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['views']

# The `StatusSerializer` class is a serializer for the `Article` model that includes the `id` and
# `status` fields.
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id','status']

# The class `ArticleUpdateSerializer` is a serializer for updating an `Article` model and includes
# fields for `article_file`, `Code`, `Abstract`, `video`, `link`, and `status`.
class ArticleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['article_file','Code','Abstract','video', 'link','status']
        
       

class ArticleCreateSerializer(serializers.ModelSerializer):
    authors = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    communities = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    unregistered_authors = serializers.ListField(child=serializers.CharField(), write_only=True)

    class Meta:
        model = Article
        fields = ['id', 'article_name','keywords', 'article_file', 'Code', 'Abstract', 'authors','video','link', 'parent_article', 'communities','unregistered_authors']
        read_only_fields = ['id']

    def create(self, validated_data):
        """
        The above function creates a new article instance with various attributes and relationships,
        including authors, communities, and parent articles.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new instance of the model. It includes the data that was passed to
        the serializer's `create` method after going through the serializer's validation process
        :return: an instance of the model `self.Meta.model`.
        """
        parent_article = validated_data.pop('parent_article', None)
        if parent_article is None:
            authors = validated_data.pop("authors", [])
            communities = validated_data.pop("communities", [])
            unregistered_authors = validated_data.pop("unregistered_authors", [])
            communities.pop(0)
            authors.pop(0)
            unregistered_authors.pop(0);
            name = validated_data.pop('article_name')
            keywords = validated_data.pop('keywords')
            keywords.replace(' ','_')
            validated_data['article_name'] = name.replace(' ','_')
            validated_data['keywords'] = keywords
            instance = self.Meta.model.objects.create(**validated_data,id=uuid.uuid4().hex)
            Author.objects.create(User=self.context['request'].user, article=instance)
            authorstr = ""
            if len(unregistered_authors)!=0:
                with transaction.atomic():
                    for author in unregistered_authors:
                        data = json.loads(author)
                        user = User.objects.filter(email=data["email"]).first()
                        if user is not None:
                            Author.objects.create(User=user, article=instance)
                            authorstr += author.User.first_name + '_' + author.User.last_name + "_"+ author.username + "||"
                        else:
                            UnregisteredUser.objects.create(email=data["email"],article = instance, fullName=data["fullName"])
                            authorstr += data["fullName"] + "||"
                        send_mail("Article added",f"You have added an article {instance.article_name} to SciCommons", settings.EMAIL_HOST_USER, [data["email"]], fail_silently=False)
        
            if len(authors)!=0:
                with transaction.atomic():
                    for author in authors:
                        author = Author.objects.create(User_id=author, article=instance)
                        authorstr += author.User.first_name + '_' + author.User.last_name + "_"+ author.username + "||"
                        send_mail("Article added",f"You have added an article {instance.article_name} to SciCommons", settings.EMAIL_HOST_USER, [author.User.email], fail_silently=False)
                        UserActivity.objects.create(user=self.context['request'].user, action=f'you added article {instance.article_name}')
            instance.authorstring = authorstr
            if len(communities) > 0 and instance.link is not None:
                raise serializers.ValidationError(detail={"error": "you can not submit external article"})

            if len(communities) > 0:
                with transaction.atomic():
                    for community in communities:
                        community_meta = CommunityMeta.objects.create(community_id=community, article=instance, status='submitted')
                        community_meta.save()
                        
                        community = Community.objects.filter(id=community).first()

                        emails = [member.user.email for member in CommunityMember.objects.filter(community_id=community)]
                        send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}', settings.EMAIL_HOST_USER, emails, fail_silently=False) 
            instance.save()
            return instance
        else:
            parentinstance = Article.objects.get(id=parent_article)
            authors = validated_data.pop("authors", [])
            unregistered_authors = validated_data.pop("unregistered_authors", [])
            authors.pop(0)
            unregistered_authors.pop(0)
            name = validated_data.pop('article_name')
            keywords = validated_data.pop('keywords')
            keywords.replace(' ','_')
            validated_data['article_name'] = name.replace(' ','_')
            validated_data['keywords'] = keywords
            instance = self.Meta.model.objects.create(**validated_data,id=uuid.uuid4().hex)
            Author.objects.create(User=self.context['request'].user, article=instance)
            authorstr = ""
            authorstr+= self.context['request'].user.first_name + '_' + self.context['request'].user.last_name + "_"+ self.context['request'].user.username + "||"
            if len(unregistered_authors)!=0:
                with transaction.atomic():
                    for author in unregistered_authors:
                        data = json.loads(author)
                        user = User.objects.filter(email=data["email"]).first()
                        if user is not None:
                            Author.objects.create(User=user, article=instance)
                            authorstr += author.User.first_name + '_' + author.User.last_name + "_"+ author.username + "||"
                        else:
                            UnregisteredUser.objects.create(email=data["email"],article = instance, fullName=data["fullName"])
                            authorstr += data["fullName"] + "||"
                        send_mail("Article added",f"You have added an article {instance.article_name} to SciCommons", settings.EMAIL_HOST_USER, [data["email"]], fail_silently=False)
        
            if len(authors)!=0:
                with transaction.atomic():
                    for author in authors:
                        author = Author.objects.create(User_id=author, article=instance)
                        authorstr += author.User.first_name + '_' + author.User.last_name + "_"+ author.username + "||"
                        send_mail("Article added",f"You have added an article {instance.article_name} to SciCommons", settings.EMAIL_HOST_USER, [author.User.email], fail_silently=False)
                        UserActivity.objects.create(user=self.context['request'].user, action=f'you added article {instance.article_name}')
            instance.authorstring = authorstr
            communities = [community for community in parentinstance.communities]
            instance.communities.set(communities)
            instance.parent_article = parent_article
            
            with transaction.atomic():
                for community in communities:
                    community_meta = CommunityMeta.objects.create(community_id=community, article=instance, status='submitted')
                    community_meta.save()
                    
                    community = Community.objects.get(id=community)

                    emails = [member.user.email for member in CommunityMember.objects.filter(community=community)]
                    send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}', settings.EMAIL_HOST_USER, emails, fail_silently=False) 
            instance.save()
            return instance
            
    
class SubmitArticleSerializer(serializers.Serializer):
    communities = serializers.ListField(child=serializers.CharField(), write_only=True)
    meta_id = serializers.ListField(child=serializers.CharField(), read_only=True)
    article_id = serializers.CharField()
    class Meta:
        fields = ['article_id','communities', 'meta_id']
        
    def create(self, validated_data):
        """
        The `create` function creates a CommunityMeta object for an Article, checks for various
        conditions, and sends email notifications to community members.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. In this case, it is expected to contain the following
        keys:
        :return: a dictionary with the key "meta_id" and the value being a list of community meta IDs.
        """

        communities = validated_data.get('communities', [])
        instance = Article.objects.filter(id=validated_data['article_id']).first()
        
        if CommunityMeta.objects.filter(article=instance).first():
            raise serializers.ValidationError(detail={"error": "article already submitted"})

        authors = Author.objects.filter(article=instance)
        
        meta_id = []
        if len(communities)==0:
            raise serializers.ValidationError(detail={"error": "communities can't be empty or None"})
        
        if len(instance.link):
            raise serializers.ValidationError(detail={"error": "you can not submit external article"})
        
        with transaction.atomic():
            for community in communities:
                admin_users = CommunityMember.objects.filter(community_id=community, is_admin=True).values_list('user_id', flat=True)
                author_users = authors.values_list('User_id', flat=True)
                intersection_users = set(admin_users) & set(author_users)
                if len(intersection_users) > 0:
                    raise serializers.ValidationError(detail={"error": "you can not submit article to community where you are admin!!!"})
                
                community_meta = CommunityMeta.objects.create(community_id=community, article=instance, status='submitted')
                community_meta.save()
                
                community = Community.objects.get(id=community)

                emails = [member.user.email for member in CommunityMember.objects.filter(community=community)]
                send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}', settings.EMAIL_HOST_USER, emails, fail_silently=False) 
                meta_id.append(community_meta.id)
        
        return {"meta_id":meta_id}

class InReviewSerializer(serializers.Serializer):
    reviewers = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True
    )
    moderator = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True
    )
    
    class Meta:
        fields = ['status', 'community', 'reviewers', 'moderator']

        
    def update(self, instance ,validated_data):
        """
        The `update` function updates the status of an article, assigns reviewers and moderators to the
        article, and sends email notifications to the assigned reviewers and moderators.
        
        :param instance: The `instance` parameter refers to the instance of the model that is being
        updated. In this case, it seems to be an instance of an article
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. It is passed to the `update` method when updating an
        instance of the serializer
        :return: a dictionary with the following keys and values:
        - "status": the status of the community_meta object after updating
        - "reviewers": the reviewers that have been added to the instance object
        - "moderator": the moderator that has been added to the instance object
        """
        request = self.context.get('request')
        community_data = request.data.get('community')
        community_meta = CommunityMeta.objects.filter(community_id=community_data, article=instance).first()
        if community_meta is None:
            raise serializers.ValidationError(detail={"error":f'article is not submitted for review {community_meta.community.Community_name}'})
        elif community_meta.status== "in review":
            raise serializers.ValidationError(detail={"error":f'article is already submitted for review'})
        elif community_meta.status == "accepted" or community_meta.status=="rejected":
            raise serializers.ValidationError(detail={"error": "article is already processed in this community"})
        
        authors = [User.id for User in Author.objects.filter(article=instance)]
        reviewers_arr = [reviewer for reviewer in OfficialReviewer.objects.filter(community_id = community_data).exclude(User__in=authors)]
        moderators_arr = [moderator for moderator in Moderator.objects.filter(community_id = community_data).exclude(user__in=authors)]

        if len(reviewers_arr)<3:
            raise serializers.ValidationError(detail={"error":"Insufficient reviewers on Community"})

        if len(moderators_arr)==0:
            raise serializers.ValidationError(detail={"error":"No Moderators on Community"})

        if len(reviewers_arr)>=3:
            reviewers_arr = random.sample(reviewers_arr, 3)

        if len(moderators_arr)>=1:
            moderators_arr = random.sample(moderators_arr, 1)
        
        community_meta.status = 'in review'
        community_meta.save()

        instance.reviewer.add(*[reviewer.id for reviewer in reviewers_arr])
        instance.moderator.add(*[moderator.id for moderator in moderators_arr])

        emails = [member.User.email for member in reviewers_arr]
        send_mail("New Article Alerts",f'You have been added as an Official Reviewer to {instance.article_name} on {community_meta.community.Community_name}', settings.EMAIL_HOST_USER, emails, fail_silently=False)

        emails = [member.user.email for member in moderators_arr]
        send_mail("New Article Alerts", f'You have been added as a Moderator to {instance.article_name} on {community_meta.community.Community_name}', settings.EMAIL_HOST_USER, emails, fail_silently=False)

        return {"status":community_meta.status, 'reviewers':instance.reviewer, 'moderator':instance.moderator}


class ApproveSerializer(serializers.Serializer):
    status = serializers.SerializerMethodField()
    community = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField(read_only=True)    
    class Meta:
        fields = ['status', 'community', 'article']

    def update(self, instance, validated_data):
        """
        The function updates the status of a community meta object, sends an email notification to the
        authors, and creates a user activity record.
        
        :param instance: The `instance` parameter refers to the instance of the model that is being
        updated. In this case, it seems to be an instance of an article model
        :param validated_data: The `validated_data` parameter is a dictionary containing the validated
        data for the serializer. It includes the data that has been validated and cleaned by the
        serializer's fields
        :return: The method is returning the updated `communitymeta` object.
        """
        request = self.context.get('request')
        community_data = request.data.get('community')
        communitymeta = CommunityMeta.objects.filter(article_id=instance.id,
                                                community_id=community_data,
                                                article=instance).first()
        communitymeta.status = 'accepted'
        communitymeta.save()
        emails = [member.email for member in instance.authors.all()]
        send_mail(f"Article is approved", f"Your article: {instance.article_name} is approved by {communitymeta.community.Community_name}", settings.EMAIL_HOST_USER , emails, fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user, action=f'you have approved the {instance.article_name} to {communitymeta.community.Community_name}')

        return communitymeta

class RejectSerializer(serializers.Serializer):
    status = serializers.SerializerMethodField()
    community = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField(read_only=True)    
    class Meta:
        fields = ['status', 'community', 'article']

    def update(self, instance, validated_data):
        """
        The function updates the status of a community meta object to 'rejected', sends an email
        notification to the authors of the article, and creates a user activity record.
        
        :param instance: The "instance" parameter refers to the instance of the model that is being
        updated. In this case, it seems to be an instance of an article model
        :param validated_data: The `validated_data` parameter is a dictionary containing the validated
        data for the serializer. It is typically used to update the instance with the new data
        :return: The method is returning the updated `communitymeta` object.
        """
        request = self.context.get('request')
        community_data = request.data.get('community')
        communitymeta = CommunityMeta.objects.filter(article_id=instance.id,
                                                community_id=community_data,
                                                article=instance).first()
        communitymeta.status = 'rejected'
        communitymeta.save()
        emails = [member.email for member in instance.authors.all()]
        send_mail(f"Article is rejected", f"Your article: {instance.article_name} is rejected by {communitymeta.community.Community_name}", settings.EMAIL_HOST_USER , emails, fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user, action=f'you have rejected the {instance.article_name} to {communitymeta.community.Community_name}')

        return communitymeta

'''
comments serializers
'''
class CommentlistSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)
    rank = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)
    userrating = serializers.SerializerMethodField(read_only=True)
    commentrating = serializers.SerializerMethodField(read_only=True)
    replies = serializers.SerializerMethodField(read_only=True)
    versions = serializers.SerializerMethodField(read_only=True)
    role = serializers.SerializerMethodField(read_only=True)
    blocked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CommentBase
        fields = ['id', 'article', 'Comment', 'Title','Type','rating','confidence', 'replies','role','blocked',
                        'tag','comment_type', 'user','Comment_date', 'commentrating', 'versions',
                    'parent_comment','rank','personal','userrating']
        
    def get_user(self, obj):
        """
        The function `get_user` returns the handle name of a user based on the given object.
        
        :param obj: The `obj` parameter is an object that contains the following attributes:
        :return: The handle_name of the first HandlersBase object that matches the User and article of
        the given obj.
        """
        handle = HandlersBase.objects.filter(User=obj.User,article=obj.article).first()
        return handle.handle_name

    def get_rank(self, obj):
        """
        The function retrieves the rank of a user and returns it as a string.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: The code is returning the rank of the user as a string.
        """
        rank = Rank.objects.filter(user=obj.User).first()
        return f'{int(rank.rank)}'
    
    def get_personal(self, obj): 
        """
        The function checks if the authenticated user is the same as the user associated with the
        object.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the object's user is the same as the request user, it returns True. Otherwise,
        it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.User == self.context['request'].user:
            return True
        else:
            return False
    
    def get_role(self,obj):
        """
        The function `get_role` determines the role of a user based on their ID and the objects
        associated with them.
        
        :param obj: The `obj` parameter is an object that represents a user. It is used to determine the
        role of the user in relation to an article
        :return: a string indicating the role of the user. The possible return values are "author",
        "reviewer", "moderator", or "none".
        """
        if obj.User_id in [author.User_id for author in Author.objects.filter(article=obj.article)]:
            return "author"
        elif (OfficialReviewer.objects.filter(User_id=obj.User_id).first() is not None) and (OfficialReviewer.objects.filter(User_id=obj.User_id).first().id in [reviewer.officialreviewer_id for reviewer in ArticleReviewer.objects.filter(article=obj.article)]):
            return "reviewer"
        elif (Moderator.objects.filter(user_id=obj.User_id).first() is not None) and (Moderator.objects.filter(user_id=obj.User_id).first().id in [member.moderator_id for member in ArticleModerator.objects.filter(article=obj.article)]):
            return "moderator"
        else:
            return "none"
    
    def get_blocked(self,obj):
        """
        The function checks if a user is blocked from accessing an article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: a boolean value. If the user ID of the given object is found in the list of user IDs of
        blocked users for the corresponding article, then it returns True. Otherwise, it returns False.
        """
        if obj.User_id in [user.user_id for user in ArticleBlockedUser.objects.filter(article=obj.article)]:
            return True
        else:
            return False
    
    def get_replies(self,obj):
        """
        The function `get_replies` returns the number of replies to a given comment object.
        
        :param obj: The `obj` parameter is an object of the `CommentBase` model
        :return: The number of CommentBase objects that have a parent_comment equal to the given obj.
        """
        member = CommentBase.objects.filter(parent_comment=obj).count()
        return member
    
    def get_commentrating(self,obj):
        """
        The function `get_commentrating` calculates the total rating of a post based on the sum of the
        values of all the likes associated with that post.
        
        :param obj: The "obj" parameter in the "get_commentrating" function is referring to the object
        for which you want to calculate the rating. It could be a post, comment, or any other object for
        which you have defined a rating system
        :return: the sum of the values of all the likes associated with the given post object.
        """
        rating = LikeBase.objects.filter(post=obj).aggregate(Sum('value'))['value__sum']
        return rating

    def get_userrating(self,obj):
        """
        The function `get_userrating` returns the rating value of a user for a given object, or 0 if the
        user is not authenticated or has not rated the object.
        
        :param obj: The `obj` parameter is referring to a post object
        :return: the user's rating for a given object. If the user is not authenticated, it returns 0.
        If the user is authenticated, it checks if the user has a rating for the object. If the user has
        a rating, it returns the rating value. If the user does not have a rating, it returns 0.
        """
        if self.context['request'].user.is_authenticated is False:
            return 0
        member = LikeBase.objects.filter(user=self.context['request'].user, post=obj).first()
        if member is not None:
            return member.value
        else:
            return 0
    
    def get_versions(self, obj):
        """
        The function "get_versions" retrieves the versions of a given object and returns the serialized
        data of the associated comments.
        
        :param obj: The `obj` parameter is an object that represents a version. It is used to filter the
        `CommentBase` objects based on the version
        :return: the serialized data of the comments that match the given version.
        """
        comment = CommentBase.objects.filter(version=obj)
        serializer = CommentSerializer(comment,many=True, context={'request': self.context['request']})
        return serializer.data

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)
    rank = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)
    userrating = serializers.SerializerMethodField(read_only=True)
    commentrating = serializers.SerializerMethodField(read_only=True)
    replies = serializers.SerializerMethodField(read_only=True)
    versions = serializers.SerializerMethodField(read_only=True)
    role = serializers.SerializerMethodField(read_only=True)
    blocked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CommentBase
        fields = ['id', 'article', 'Comment', 'Title', 'Type', 'tag','comment_type', 'user','Comment_date', 'versions', 'role', 'blocked',
                    'parent_comment','rank','personal', 'replies', 'rating','confidence','version','commentrating','userrating']
        
    def get_user(self, obj):
        """
        The function `get_user` returns the handle name of a user based on the given object.
        
        :param obj: The `obj` parameter is an object that contains the following attributes:
        :return: The handle_name of the first HandlersBase object that matches the User and article of
        the given obj.
        """
        handle = HandlersBase.objects.filter(User=obj.User,article=obj.article).first()
        return handle.handle_name

    def get_rank(self, obj):
        """
        The function retrieves the rank of a user and returns it as a string.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: The code is returning the rank of the user as a string.
        """
        rank = Rank.objects.filter(user=obj.User).first()
        return f'{int(rank.rank)}'
    
    def get_personal(self, obj):
        """
        The function checks if the authenticated user is the same as the user associated with the
        object.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the object's user is the same as the request user, it returns True. Otherwise,
        it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.User == self.context['request'].user:
            return True
        else:
            return False
        
    def get_blocked(self,obj):
        """
        The function checks if a user is blocked from accessing an article.
        
        :param obj: The `obj` parameter is an object that represents an article
        :return: a boolean value. If the user ID of the given object is found in the list of user IDs of
        blocked users for the corresponding article, then it returns True. Otherwise, it returns False.
        """
        if obj.User_id in [user.user_id for user in ArticleBlockedUser.objects.filter(article=obj.article)]:
            return True
        else:
            return False
    
    def get_role(self,obj):
        """
        The function `get_role` determines the role of a user based on their ID and the objects
        associated with them.
        
        :param obj: The `obj` parameter is an object that represents a user. It is used to determine the
        role of the user in relation to an article
        :return: a string indicating the role of the user. The possible return values are "author",
        "reviewer", "moderator", or "none".
        """
        if obj.User_id in [author.User_id for author in Author.objects.filter(article=obj.article)]:
            return "author"
        elif (OfficialReviewer.objects.filter(User_id=obj.User_id).first() is not None) and (OfficialReviewer.objects.filter(User_id=obj.User_id).first().id in [reviewer.officialreviewer_id for reviewer in ArticleReviewer.objects.filter(article=obj.article)]):
            return "reviewer"
        elif (Moderator.objects.filter(user_id=obj.User_id).first() is not None) and (Moderator.objects.filter(user_id=obj.User_id).first().id in [member.moderator_id for member in ArticleModerator.objects.filter(article=obj.article)]):
            return "moderator"
        else:
            return "none"
        
    def get_replies(self,obj):
        """
        The function `get_replies` returns the number of replies to a given comment object.
        
        :param obj: The `obj` parameter is an object of the `CommentBase` model
        :return: The number of CommentBase objects that have a parent_comment equal to the given obj.
        """
        member = CommentBase.objects.filter(parent_comment=obj).count()
        return member
    
    def get_commentrating(self,obj):
        """
        The function `get_commentrating` calculates the total rating of a post based on the sum of the
        values of all the likes associated with that post.
        
        :param obj: The "obj" parameter in the "get_commentrating" function is referring to the post
        object for which you want to calculate the rating
        :return: the sum of the values of all the likes associated with the given post object.
        """
        rating = LikeBase.objects.filter(post=obj).aggregate(Sum('value'))['value__sum']
        return rating

    def get_userrating(self,obj):
        """
        The function `get_userrating` returns the rating value of a user for a given object, or 0 if the
        user is not authenticated or has not rated the object.
        
        :param obj: The `obj` parameter is referring to a post object
        :return: the user's rating for a given object. If the user is not authenticated, it returns 0.
        If the user is authenticated, it checks if the user has a rating for the object. If the user has
        a rating, it returns the rating value. If the user does not have a rating, it returns 0.
        """
        if self.context['request'].user.is_authenticated is False:
            return 0
        member = LikeBase.objects.filter(user=self.context['request'].user, post=obj).first()
        if member is not None:
            return member.value
        else:
            return 0
    
    def get_versions(self, obj):
        """
        The function `get_versions` retrieves the versions of a given object and returns the serialized
        data of the associated comments.
        
        :param obj: The `obj` parameter is an object that represents a version. It is used to filter the
        `CommentBase` objects based on their version
        :return: the serialized data of the comments that match the given version.
        """
        comment = CommentBase.objects.filter(version=obj)
        serializer = CommentSerializer(comment,many=True, context={"request": self.context['request']})
        return serializer.data


class CommentCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CommentBase
        fields = ['id', 'article', 'Comment', 'Title', 'Type', 'tag','comment_type','parent_comment','rating','confidence','version']
        read_only_fields = ['id']

    def create(self, validated_data):
        """
        The `create` function creates a comment instance based on the validated data and saves it to the
        database, while also handling notifications and sending emails to relevant users.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new instance of the model. It typically includes the data that was
        submitted in the request and has been validated by the serializer
        :return: The `instance` object is being returned.
        """
        authors = [author for author in Author.objects.filter(article=validated_data["article"],User=self.context["request"].user)]
        reviewers_arr = [reviewer for reviewer in ArticleReviewer.objects.filter(article=validated_data["article"],officialreviewer__User = self.context["request"].user)]
        moderators_arr = [moderator for moderator in ArticleModerator.objects.filter(article=validated_data["article"],moderator__user = self.context["request"].user)]

        if len(authors)> 0 or len(reviewers_arr)>0 or len(moderators_arr)>0:
            validated_data["comment_type"] = "OfficialComment"
        else:
            validated_data["comment_type"] = "PublicComment"
        instance = self.Meta.model.objects.create(**validated_data,User=self.context["request"].user)
        instance.save()
        
        handler = HandlersBase.objects.filter(User=instance.User, article=instance.article).first()
        
        if not handler: 
            handler = HandlersBase.objects.create(User=instance.User, article=instance.article, handle_name=fake.name())
            handler.save()
        
        handler = HandlersBase.objects.filter(User=instance.User, article=instance.article).first()

        if validated_data["parent_comment"]:
            member = CommentBase.objects.filter(id=validated_data['parent_comment'].id).first()
            notification = Notification.objects.create(user=member.User, message=f'{handler.handle_name} replied to your comment on {member.article.article_name} ', link=f'/article/{member.article.id}/{instance.id}')
            notification.save()
            send_mail(f"somebody replied to your comment",f"{handler.handle_name} have made a replied to your comment.checkout this {parse(config('CLIENT_URL'))}/article/{member.article.id}/{instance.id}", settings.EMAIL_HOST_USER,[member.User.email], fail_silently=False)

        if validated_data["Type"] == "review" or validated_data["Type"] == "decision":
            emails = [author.User.email for author in authors ]
            for author in authors:
                notification = Notification.objects.create(user=author.User, message=f'{handler.handle_name} has added a {validated_data["Type"]} to your article: {instance.article.article_name} ', link=f'/article/{member.article.id}/{instance.id}')
                notification.save()
            send_mail(f"A new {validated_data['Type']} is added ",f"{handler.handle_name} has added a {validated_data['Type']} to your article: {instance.article.article_name}. checkout this {parse(config('CLIENT_URL'))}/article/{member.article.id}/{instance.id}", settings.EMAIL_HOST_USER,emails, fail_silently=False)

            
        send_mail(f"you have made {instance.Type}",f"You have made a {instance.Type} on {instance.article.article_name}. checkout this {parse(config('CLIENT_URL'))}/article/{member.article.id}/{instance.id}", settings.EMAIL_HOST_USER,[instance.User.email], fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user, action=f"You have made a {instance.Type} on {instance.article.article_name}")

        return instance    
        
class CommentUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CommentBase
        fields = ['Comment', 'Title']
        
class LikeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = LikeBase
        fields = ['post', 'value']

'''
Article Chat Serializers
'''
class ArticleChatSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ArticleMessage
        fields = ["id", "sender", "body", "media", "article", "created_at", "personal"]

    def get_sender(self, obj):
        """
        The function `get_sender` takes an object and returns the username of the sender associated with
        that object.
        
        :param obj: The `obj` parameter is an object that represents the sender of a message
        :return: the username of the sender of the given object.
        """
        user = User.objects.filter(id=obj.sender.id).first()
        return f"{user.username}"

    def get_personal(self,obj):
        """
        The function checks if the authenticated user is the sender of a given object.
        
        :param obj: The `obj` parameter is an object that represents some kind of data or model
        instance. It is used to check if the sender of the object is the same as the authenticated user
        making the request
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the sender of the object is the same as the authenticated user, it returns
        True. Otherwise, it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.sender == self.context['request'].user:
            return True
        else:
            return False


class ArticleChatUpdateSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ArticleMessage
        fields = ["body", "media", "sender"]


class ArticleChatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleMessage
        fields = ["id","body", "article"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        """
        The function creates a new instance of a model, assigns a related article and channel, and saves
        it.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new instance of the model. It typically includes the data that was
        submitted in a request and has been validated against the model's fields
        :return: The instance of the created object is being returned.
        """
        article_id = validated_data.get("article")
        print(article_id)
        validated_data.pop("article")
        article = Article.objects.filter(article_name=article_id).first()
        channel = f"{article.id}"

        instance = self.Meta.model.objects.create(
            **validated_data, article=article, channel=channel, sender=self.context["request"].user
        )
        instance.save()

        return instance

 
'''
notification serializer
'''
class NotificationSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Notification
        fields = ["id", "user", "message", "date", "is_read", "link"]
        
'''
favourite serializer
'''
class FavouriteSerializer(serializers.ModelSerializer):
    article_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Favourite
        fields = ['id', 'article_name', 'user']
        
    def get_article_name(self, obj):
        return obj.article.article_name

class FavouriteCreateSerializer(serializers.Serializer):
    article_name = serializers.CharField(write_only=True)

    class Meta:
        model = Favourite
        fields = ['id', 'article', 'user']
        read_only_fields = ['id']
        
    def create(self, validated_data):
        """
        The function creates a new Favourite object if it doesn't already exist and logs the user's
        activity.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for the serializer fields. In this case, it is expected to contain the following
        keys:
        :return: The `create` method returns an instance of the `Favourite` model that was created.
        """
        
        favourite = Favourite.objects.filter(article=validated_data['article'],
                                           user=self.context['request'].user).first()
        if favourite:
            raise serializers.ValidationError({"error":"already in favourites"})
        
        instance = Favourite.objects.create(article=validated_data['article'],
                                           user=self.context['request'].user)
        instance.save()
        UserActivity.objects.create(user=self.context['request'].user, action=f"You added {instance.article.article_name} in favourite")

        return instance
               
'''
communitymeta serializers
'''
class CommunityMetaSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CommunityMeta
        fields = ['community', 'article', 'status']
        depth = 1

class CommunityMetaArticlesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMeta
        fields = ['article','status']
        depth = 1

class CommunityMetaApproveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMeta
        fields = ['community', 'status']
        depth = 1

'''
communitymembers serializer
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
        fields = ['username','is_reviewer','is_moderator','is_admin', 'profile_pic_url', 'user_id','email']
    
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
AuthorSerializer
'''
class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['article']
        depth = 1

'''
OfficialReviewerSerializer
'''
class OfficialReviewerSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialReviewer
        fields = ['User','community']
        depth = 1

'''
ModeratorSerializer
'''
class ModeratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Moderator
        fields = ['user','community']
        depth = 1


class SocialPostSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = SocialPost
        fields = ['id', 'user', 'body', 'created_at', 'image']
        read_only_fields = ['user','id','created_at', 'image']
    
    def get_image(self, obj):
        if obj.image:
            url = obj.image.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'


class SocialPostUpdateSerializer(serializers.ModelSerializer):
    body = serializers.CharField(required=False)
    image = serializers.ImageField(required=False)

    class Meta:
        model = SocialPost
        fields = ['id', 'user', 'body', 'created_at','image']
        read_only_fields = ['user','id','created_at']

    def update(self, instance, validated_data):
        """
        The function updates the attributes of an instance with the values from a validated data
        dictionary and saves the instance.
        
        :param instance: The `instance` parameter refers to the object that you want to update. It could
        be an instance of a model or any other object that you want to modify
        :param validated_data: A dictionary containing the validated data that needs to be updated in
        the instance
        :return: The updated instance is being returned.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class SocialPostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPost
        fields = ['id', 'user', 'body', 'created_at', 'image']
        read_only_fields = ['user','id','created_at']

    def create(self, validated_data):
        """
        The function creates a new instance of a model with the provided validated data and associates
        it with the current user.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data for creating a new instance of the model. This data is typically obtained from
        the request data after it has been validated by the serializer
        :return: The instance that was created and saved.
        """
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.save()
        return instance

class SocialPostListSerializer(serializers.ModelSerializer):
    comments_count = serializers.SerializerMethodField(read_only=True)
    likes = serializers.SerializerMethodField(read_only=True)
    liked = serializers.SerializerMethodField(read_only=True)
    bookmarks = serializers.SerializerMethodField(read_only=True)
    isbookmarked = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)
    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialPost
        fields = ['id', 'username', 'body', 'created_at', 'comments_count', 'likes', 'liked', 'bookmarks','avatar', 'isbookmarked', 'image','personal']

    def get_username(self,obj):
        """
        The function `get_username` returns the username of a given object's user attribute.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username
    
    def get_avatar(self,obj):
        """
        The function `get_avatar` returns the profile picture URL of a user.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute, which in turn has a
        `profile_pic_url` method
        :return: the profile picture URL of the user.
        """
        if obj.user.profile_pic_url:
            url = obj.user.profile_pic_url.url.split('?')[0]
            return url
        return 'https://scicommons.s3.awsamazon.com/None'

    def get_image(self, obj):
        if obj.image:
            url = obj.image.url.split('?')[0]
            return url
        return 'https://scicommons.s3.awsamazon.com/None'

    def get_comments_count(self, obj):
        """
        The function `get_comments_count` returns the count of top-level comments for a given
        `SocialPostComment` object.
        
        :param obj: The `obj` parameter is an object that represents a social post
        :return: the count of comments on a social post object.
        """
        comments_count = SocialPostComment.objects.filter(post_id=obj.id,parent_comment=None).count()
        return comments_count
    
    def get_likes(self, obj):
        """
        The function "get_likes" returns the number of likes for a given social post object.
        
        :param obj: The `obj` parameter is an object that represents a social post
        :return: The number of likes for the given object.
        """
        likes = SocialPostLike.objects.filter(post_id=obj.id).count()
        return likes

    def get_liked(self, obj):
        """
        The function `get_liked` checks if a user has liked a social post.
        
        :param obj: The `obj` parameter is an object that represents a social post
        :return: the count of SocialPostLike objects where the post_id matches the id of the given obj
        and the user is the authenticated user making the request.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        liked = SocialPostLike.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
        return liked
    
    def get_personal(self,obj):
        """
        The function checks if the authenticated user is the same as the user associated with the object.
        
        :param obj: The "obj" parameter is an object that represents some kind of personal data or
        resource. It could be a user profile, a document, or any other object that is associated with a
        specific user
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the object's user is the same as the request user, it returns True. Otherwise,
        it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.user == self.context['request'].user:
            return True
        else:
            return False
    

    def get_bookmarks(self,obj):
        """
        The function "get_bookmarks" returns the number of bookmarks for a given post.
        
        :param obj: The `obj` parameter is an object that represents a post
        :return: The number of bookmarks associated with the given object.
        """
        bookmarks = BookMark.objects.filter(post_id=obj.id).count()
        return bookmarks

    def get_isbookmarked(self,obj):
        """
        The function `get_isbookmarked` checks if a user has bookmarked a specific post.
        
        :param obj: The `obj` parameter is an object that represents a post
        :return: the value of the variable "isbookmarked".
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        isbookmarked = BookMark.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
        return isbookmarked

class SocialPostGetSerializer(serializers.ModelSerializer):
    comments = serializers.SerializerMethodField(read_only=True)
    comments_count = serializers.SerializerMethodField(read_only=True)
    likes = serializers.SerializerMethodField(read_only=True)
    liked = serializers.SerializerMethodField(read_only=True)
    bookmarks = serializers.SerializerMethodField(read_only=True)
    isbookmarked = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)
    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialPost
        fields = ['id', 'username', 'body', 'created_at', 'comments_count', 'likes', 'liked', 'comments', 'bookmarks','avatar', 'isbookmarked', 'image','personal']

    def get_username(self,obj):
        """
        The function `get_username` returns the username of a given object's user attribute.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username
    
    def get_avatar(self,obj):
        """
        The function `get_avatar` returns the profile picture URL of a user.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute is
        expected to have a `profile_pic_url` method that returns the URL of the user's profile picture
        :return: the profile picture URL of the user.
        """
        if obj.user.profile_pic_url:
            url = obj.user.profile_pic_url.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_image(self, obj):
        if obj.image:
            url = obj.image.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_comments(self, obj):
        """
        The function `get_comments` retrieves the top-level comments for a given post object and returns
        them serialized.
        
        :param obj: The `obj` parameter is an object that represents a social post. It is used to filter
        the comments based on the post's ID
        :return: the serialized data of the comments that meet the specified criteria.
        """
        comments = SocialPostComment.objects.filter(post_id=obj.id, parent_comment__isnull=True).order_by('-created_at')
        serializer = SocialPostCommentListSerializer(comments, many=True, context={'request': self.context['request']})
        return serializer.data

    def get_comments_count(self, obj):
        """
        The function `get_comments_count` returns the number of comments for a given `obj` (presumably a
        social post).
        
        :param obj: The `obj` parameter is an object that represents a social post
        :return: the count of comments for a given post object.
        """
        comments_count = SocialPostComment.objects.filter(post_id=obj.id).count()
        return comments_count
    
    def get_personal(self,obj):
        """
        The function checks if the authenticated user is the same as the user associated with the object.
        
        :param obj: The "obj" parameter is an object that represents some kind of personal data or
        resource. It could be a user profile, a document, or any other object that is associated with a
        specific user
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the object's user is the same as the request user, it returns True. Otherwise,
        it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.user == self.context['request'].user:
            return True
        else:
            return False
    
    def get_likes(self, obj):
        """
        The function "get_likes" returns the number of likes for a given social post object.
        
        :param obj: The `obj` parameter is an object that represents a social post
        :return: The number of likes for the given object.
        """
        likes = SocialPostLike.objects.filter(post_id=obj.id).count()
        return likes

    def get_liked(self, obj):
        """
        The function `get_liked` checks if a user has liked a social post.
        
        :param obj: The `obj` parameter is an object that represents a post. It is used to filter the
        `SocialPostLike` objects based on the `post_id` field
        :return: the count of SocialPostLike objects where the post_id matches the id of the given obj
        and the user is the authenticated user making the request.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        liked = SocialPostLike.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
        return liked
    
    def get_bookmarks(self,obj):
        """
        The function "get_bookmarks" returns the number of bookmarks associated with a given post object.
        
        :param obj: The `obj` parameter is an object that represents a post
        :return: The number of bookmarks associated with the given object.
        """
        bookmarks = BookMark.objects.filter(post_id=obj.id).count()
        return bookmarks

    def get_isbookmarked(self,obj):
        """
        The function `get_isbookmarked` checks if a user has bookmarked a specific post.
        
        :param obj: The `obj` parameter is an object that represents a post. It is used to check if the
        post is bookmarked by the current user
        :return: the value of the variable "isbookmarked".
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        isbookmarked = BookMark.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
        return isbookmarked


class SocialPostCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at']
        read_only_fields = ['user','id','created_at']

class SocialPostCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at','parent_comment']
        read_only_fields = ['user','id','created_at']

    def create(self, validated_data):
        """
        The function creates a new instance of a model with the provided validated data and associates it
        with the current user.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the validated
        data that is passed to the `create` method. This data is typically obtained from the request
        payload and has been validated against the serializer's fields
        :return: The instance that was created and saved.
        """
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.save()
        if instance.parent_comment is None:
            notification = Notification.objects.create(user=instance.User, message=f'someone replied to your post on {parse(config("CLIENT_URL"))} ', link=f'/article/{member.article.id}/{instance.id}')
            notification.save()
        return instance
    
class SocialPostCommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at','parent_comment']
        read_only_fields = ['user','id','created_at','post']

    def update(self, instance, validated_data):
        """
        The function updates the comment attribute of an instance with the value provided in the
        validated_data dictionary.
        
        :param instance: The `instance` parameter refers to the object that you want to update. It is
        the instance of the model that you are working with
        :param validated_data: The `validated_data` parameter is a dictionary that contains the
        validated data that was passed to the serializer. It typically includes the data that was sent
        in the request payload after it has been validated and cleaned by the serializer
        :return: The updated instance is being returned.
        """
        instance.comment = validated_data.get('comment', instance.comment)
        instance.save()
        return instance

class SocialPostCommentListSerializer(serializers.ModelSerializer):

    commentlikes = serializers.SerializerMethodField(read_only=True)
    commentliked = serializers.SerializerMethodField(read_only=True)
    commentavatar = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    replies = serializers.SerializerMethodField(read_only=True)
    personal = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialPostComment
        fields = ['id', 'username', 'post', 'comment', 'created_at', 'commentlikes', 'commentliked', 'commentavatar','replies', 'personal']
    
    def get_username(self,obj):
        """
        The function `get_username` returns the username of a given object's user.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute is
        expected to have a `username` attribute
        :return: The username of the user object.
        """
        return obj.user.username
    
    def get_commentavatar(self,obj):
        """
        The function `get_commentavatar` returns the profile picture URL of the user associated with the
        given object.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: the profile picture URL of the user associated with the given object.
        """
        if obj.user.profile_pic_url:
            url = obj.user.profile_pic_url.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'

    def get_commentlikes(self, obj):
        """
        The function "get_commentlikes" returns the number of likes for a given comment.
        
        :param obj: The `obj` parameter is an instance of the `SocialPostComment` model
        :return: The number of likes on a social post comment with the given object ID.
        """
        likes = SocialPostCommentLike.objects.filter(comment_id=obj.id).count()
        return likes
    
    def get_commentliked(self, obj):
        """
        The function "get_commentliked" checks if the authenticated user has liked a specific comment.
        
        :param obj: The `obj` parameter is the comment object for which we want to check if the
        authenticated user has liked it or not
        :return: the number of likes for a specific comment made by the authenticated user.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        liked = SocialPostCommentLike.objects.filter(comment_id=obj.id, user=self.context['request'].user).count()
        return liked
    
    def get_personal(self,obj):
        """
        The function checks if the authenticated user is the same as the user associated with the object.
        
        :param obj: The `obj` parameter is an object that represents some kind of personal data or
        resource. It could be a user profile, a document, or any other object that is associated with a
        specific user
        :return: a boolean value. If the user is not authenticated, it returns False. If the user is
        authenticated and the object's user is the same as the request user, it returns True. Otherwise,
        it returns False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        if obj.user == self.context['request'].user:
            return True
        else:
            return False    
    
    def get_replies(self,obj):
        """
        The function "get_replies" returns the number of replies for a given comment object.
        
        :param obj: The `obj` parameter is an instance of the `SocialPostComment` model
        :return: The number of replies to the given object.
        """
        replies = SocialPostComment.objects.filter(parent_comment=obj).count()
        return replies

    
class SocialPostLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostLike
        fields = ['id', 'user', 'post']
        read_only_fields = ['user','id']


class SocialPostCommentLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostCommentLike
        fields = ['id', 'user', 'comment']
        read_only_fields = ['user','id']


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user']
        read_only_fields = ['user','id']

class FollowersSerializer(serializers.ModelSerializer):

    avatar = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    isFollowing = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user','avatar', 'username','isFollowing']
        read_only_fields = ['user', 'id']
    
    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user.
        
        :param obj: The parameter "obj" is an object that is passed to the function. It is expected to have
        a property called "user" which is also an object. The "user" object is expected to have a property
        called "username". The function returns the value of the "username" property of the
        :return: The username of the user object.
        """
        return obj.user.username
    
    def get_avatar(self, obj):
        """
        The function `get_avatar` returns the profile picture URL of a user object.
        
        :param obj: The `obj` parameter is an object that has a `user` attribute, which in turn has a
        `profile_pic_url` method
        :return: the profile picture URL of the user object.
        """
        if obj.user.profile_pic_url:
            url = obj.user.profile_pic_url.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_isFollowing(self, obj):
        """
        The function checks if a user is following another user and returns True if they are, and False if
        they are not.
        
        :param obj: The `obj` parameter is an object that represents a user
        :return: a boolean value. If the user is authenticated and is following the specified object, it
        will return True. Otherwise, it will return False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        member = Follow.objects.filter(user=self.context['request'].user, followed_user=obj.user).first()
        if member is not None:
            return True
        else:
            return False

class FollowingSerializer(serializers.ModelSerializer):

    avatar = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    isFollowing = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user','avatar', 'username','isFollowing']
        read_only_fields = ['user', 'id']
    
    def get_username(self, obj):
        """
        The function `get_username` takes an object `obj` and returns the username of the followed user.
        
        :param obj: The `obj` parameter is an object that represents a followed user
        :return: The username of the followed user.
        """
        return obj.followed_user.username
    
    def get_avatar(self, obj):
        """
        The function `get_avatar` takes an object `obj` and returns the profile picture URL of the user
        that `obj` is following.
        
        :param obj: The `obj` parameter is an object that represents a followed user
        :return: the profile picture URL of the followed user.
        """
        if obj.followed_user.profile_pic_url:
            url = obj.followed_user.profile_pic_url.url.split('?')[0]
            return url
    
        return 'https://scicommons.s3.amazonaws.com/None'
    
    def get_isFollowing(self, obj):
        """
        The function checks if a user is following another user.
        
        :param obj: The `obj` parameter is an object that represents the user being followed
        :return: a boolean value. If the user is authenticated and there is a Follow object with the user
        and the followed_user specified, it will return True. Otherwise, it will return False.
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        member = Follow.objects.filter(user=self.context['request'].user, followed_user=obj.followed_user).first()
        if member is not None:
            return True
        else:
            return False

class FollowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user']
        read_only_fields = ['user','id']

    def create(self, validated_data):
        """
        The function creates a new instance of a model with the provided validated data and associates it
        with the current user.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the validated
        data that was passed to the serializer. This data has already been validated and is ready to be
        used to create a new instance of the model
        :return: The instance that was created and saved.
        """
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.save()
        return instance

class SocialPostBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookMark
        fields = ['id', 'user', 'post']
        read_only_fields = ['user','id']

class SocialPostBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookMark
        fields = ['id', 'user', 'post']
        read_only_fields = ['user','id']

    def create(self, validated_data):
        """
        The function creates a new instance of a model with the provided validated data and associates it
        with the current user.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the validated
        data for creating a new instance of the model. This data has been validated against the model's
        fields and any validation rules defined in the serializer
        :return: The instance that was created and saved.
        """
        instance = self.Meta.model.objects.create(**validated_data, user=self.context['request'].user)
        instance.save()
        return instance
    
'''
Message Serailizer
'''
    
class MessageSerializer(serializers.ModelSerializer):
    receiver = serializers.SerializerMethodField(read_only=True)
    sender = serializers.SerializerMethodField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PersonalMessage
        fields = ["id","sender", "receiver", "media", "body", "created_at", "avatar","channel"]

    def get_receiver(self, obj):
        """
        The function `get_receiver` takes an object as input and returns the username of the receiver of
        that object.
        
        :param obj: The `obj` parameter is an object that has a `receiver` attribute. The `receiver`
        attribute is expected to be an object with an `id` attribute
        :return: The username of the user associated with the receiver object.
        """

        user = User.objects.filter(id=obj.receiver.id).first()
        return f"{user.username}"
    
    def get_sender(self,obj):
        """
        The function `get_sender` takes an object `obj` and returns the username of the sender of that
        object.
        
        :param obj: The `obj` parameter is an object that represents the sender of a message
        :return: the username of the sender of the given object.
        """
        user = User.objects.filter(id=obj.sender.id).first()
        return f"{user.username}"
    
    def get_avatar(self,obj):
        """
        The function `get_avatar` returns the profile picture URL of the sender if the sender is the
        current user, otherwise it returns the profile picture URL of the receiver.
        
        :param obj: The `obj` parameter is an object that represents a message. It likely has attributes
        such as `sender` and `receiver`, which are objects representing the sender and receiver of the
        message
        :return: the profile picture URL of either the receiver or the sender, depending on whether the
        sender is the current user or not.
        """
        if obj.sender == self.context['request'].user:
            if obj.receiver.profile_pic_url:
                url = obj.receiver.profile_pic_url.url.split('?')[0]
                return url
            return 'https://scicommons.s3.amazonaws.com/None'
        else:
            if obj.sender.profile_pic_url:
                url = obj.sender.profile_pic_url.url.split('?')[0]
                return url
            return 'https://scicommons.s3.amazonaws.com/None'



class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalMessage
        fields = ["body", "media"]


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalMessage
        fields = ["body", "receiver", "media"]

    def create(self, validated_data):
        """
        The function creates a chat instance, saves it to the database, and sends a message via
        websockets to a specific channel.
        
        :param validated_data: The `validated_data` parameter is a dictionary that contains the validated
        data for creating a new instance of the model. It typically includes the data that was submitted
        in a request and has been validated against the model's fields
        :return: The instance of the created object is being returned.
        """
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        receiver = validated_data("receiver", None)

        temp = [f"{self.context['request'].user}",f"{receiver}"]
        temp.sort()
        channel = f"chat_{temp[0]}_{temp[1]}"

        instance = self.Meta.model.objects.create(
            **validated_data, channel=channel, sender=self.context["request"].user
        )
        instance.save()

        if receiver:
            message = {
                "sender": instance.sender,
                "receiver": instance.receiver,
                "body": instance.body,
                "media":instance.media.url
            }

        # Send the message via websockets
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            channel, {"type": "chat_message", "message": message}
        )

        return instance
    
class MessageListSerializer(serializers.ModelSerializer):
    receiver = serializers.SerializerMethodField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)
    unread_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PersonalMessage
        fields = ["id", "receiver", "media", "body", "created_at", "avatar","channel", "unread_count"]

    def get_receiver(self, obj):
        """
        The function returns the username of the receiver of a message object, based on the sender and
        the current user.
        
        :param obj: The `obj` parameter is an object that has a `sender` and `receiver` attribute. These
        attributes are expected to be instances of the `User` model
        :return: the username of the receiver or sender, depending on the condition.
        """
        if obj.sender == self.context['request'].user:
            user = User.objects.filter(id=obj.receiver.id).first()
            return f"{user.username}"
        user = User.objects.filter(id=obj.sender.id).first()
        return f"{user.username}"
    
    def get_avatar(self,obj):
        """
        The function `get_avatar` returns the profile picture URL of the sender if the sender is the
        current user, otherwise it returns the profile picture URL of the receiver.
        
        :param obj: The `obj` parameter is an object that represents a message. It is used to determine
        the sender and receiver of the message
        :return: the profile picture URL of either the receiver or the sender, depending on whether the
        sender is the current user or not.
        """
        if obj.sender == self.context['request'].user:
            if obj.receiver.profile_pic_url:
                url = obj.receiver.profile_pic_url.url.split('?')[0]
                return url
            return 'https://scicommons.s3.amazonaws.com/None'
        else:
            if obj.sender.profile_pic_url:
                url = obj.sender.profile_pic_url.url.split('?')[0]
                return url
            return 'https://scicommons.s3.amazonaws.com/None'

    def get_unread_count(self,obj):
        """
        The function `get_unread_count` returns the number of unread personal messages for a given user.
        
        :param obj: The `obj` parameter is not used in the code snippet provided. It seems to be unused
        and can be removed from the method signature
        :return: the count of unread personal messages for the specified user.
        """
        count = PersonalMessage.objects.filter(Q(sender=self.context['request'].user) | Q(receiver=self.context['request'].user), is_read=False).count()
        return count

