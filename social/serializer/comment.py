from rest_framework import serializers

from social.models import SocialPostComment, SocialPostCommentLike
from user.models import Notification


class SocialPostCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at']
        read_only_fields = ['user', 'id', 'created_at']


class SocialPostCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at', 'parent_comment']
        read_only_fields = ['user', 'id', 'created_at']

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
            notification = Notification.objects.create(user=instance.user, message=f'someone replied to your post',
                                                       link=f'/post/{instance.post.id}/{instance.id}')
            notification.save()
        return instance


class SocialPostCommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostComment
        fields = ['id', 'user', 'post', 'comment', 'created_at', 'parent_comment']
        read_only_fields = ['user', 'id', 'created_at', 'post']

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
        fields = ['id', 'username', 'post', 'comment', 'created_at', 'commentlikes', 'commentliked', 'commentavatar',
                  'replies', 'personal']

    def get_username(self, obj):
        """
        The function `get_username` returns the username of a given object's user.

        :param obj: The `obj` parameter is an object that has a `user` attribute. The `user` attribute is
        expected to have a `username` attribute
        :return: The username of the user object.
        """
        return obj.user.username

    def get_commentavatar(self, obj):
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

    def get_personal(self, obj):
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

    def get_replies(self, obj):
        """
        The function "get_replies" returns the number of replies for a given comment object.

        :param obj: The `obj` parameter is an instance of the `SocialPostComment` model
        :return: The number of replies to the given object.
        """
        replies = SocialPostComment.objects.filter(parent_comment=obj).count()
        return replies


class SocialPostCommentLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostCommentLike
        fields = ['id', 'user', 'comment']
        read_only_fields = ['user', 'id']
