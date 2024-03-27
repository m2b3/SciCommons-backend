from rest_framework import serializers

from social.models import Follow


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user']
        read_only_fields = ['user', 'id']


class FollowersSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField(read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    isFollowing = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'user', 'followed_user', 'avatar', 'username', 'isFollowing']
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
        fields = ['id', 'user', 'followed_user', 'avatar', 'username', 'isFollowing']
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
        read_only_fields = ['user', 'id']

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
