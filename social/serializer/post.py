from rest_framework import serializers

from social.models import SocialPost, SocialPostComment, SocialPostLike, Bookmark

class SocialPostSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SocialPost
        fields = ['id', 'user', 'body', 'created_at', 'image']
        read_only_fields = ['user', 'id', 'created_at', 'image']

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
        fields = ['id', 'user', 'body', 'created_at', 'image']
        read_only_fields = ['user', 'id', 'created_at']

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
        read_only_fields = ['user', 'id', 'created_at']

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
        fields = ['id', 'username', 'body', 'created_at', 'comments_count', 'likes', 'liked', 'bookmarks', 'avatar',
                  'isbookmarked', 'image', 'personal']

    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user attribute.

        :param obj: The `obj` parameter is an object that has a `user` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username

    def get_avatar(self, obj):
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
        comments_count = SocialPostComment.objects.filter(post_id=obj.id, parent_comment=None).count()
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

    def get_personal(self, obj):
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

    def get_bookmarks(self, obj):
        """
        The function "get_bookmarks" returns the number of bookmarks for a given post.

        :param obj: The `obj` parameter is an object that represents a post
        :return: The number of bookmarks associated with the given object.
        """
        bookmarks = Bookmark.objects.filter(post_id=obj.id).count()
        return bookmarks

    def get_isbookmarked(self, obj):
        """
        The function `get_isbookmarked` checks if a user has bookmarked a specific post.

        :param obj: The `obj` parameter is an object that represents a post
        :return: the value of the variable "isbookmarked".
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        isbookmarked = Bookmark.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
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
        fields = ['id', 'username', 'body', 'created_at', 'comments_count', 'likes', 'liked', 'comments', 'bookmarks',
                  'avatar', 'isbookmarked', 'image', 'personal']

    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user attribute.

        :param obj: The `obj` parameter is an object that has a `user` attribute
        :return: The username of the user associated with the given object.
        """
        return obj.user.username

    def get_avatar(self, obj):
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
        from social.serializer import SocialPostCommentListSerializer

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

    def get_personal(self, obj):
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

    def get_bookmarks(self, obj):
        """
        The function "get_bookmarks" returns the number of bookmarks associated with a given post object.

        :param obj: The `obj` parameter is an object that represents a post
        :return: The number of bookmarks associated with the given object.
        """
        bookmarks = Bookmark.objects.filter(post_id=obj.id).count()
        return bookmarks

    def get_isbookmarked(self, obj):
        """
        The function `get_isbookmarked` checks if a user has bookmarked a specific post.

        :param obj: The `obj` parameter is an object that represents a post. It is used to check if the
        post is bookmarked by the current user
        :return: the value of the variable "isbookmarked".
        """
        if self.context['request'].user.is_authenticated is False:
            return False
        isbookmarked = Bookmark.objects.filter(post_id=obj.id, user=self.context['request'].user).count()
        return isbookmarked


class SocialPostLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostLike
        fields = ['id', 'user', 'post']
        read_only_fields = ['user', 'id']


class SocialPostBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'post']
        read_only_fields = ['user', 'id']

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
