from django.db.models import Q
from rest_framework import serializers

from chat.models import PersonalMessage
from user.models import User


class MessageSerializer(serializers.ModelSerializer):
    receiver = serializers.SerializerMethodField(read_only=True)
    sender = serializers.SerializerMethodField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PersonalMessage
        fields = ["id", "sender", "receiver", "media", "body", "created_at", "avatar", "channel"]

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

    def get_sender(self, obj):
        """
        The function `get_sender` takes an object `obj` and returns the username of the sender of that
        object.

        :param obj: The `obj` parameter is an object that represents the sender of a message
        :return: the username of the sender of the given object.
        """
        user = User.objects.filter(id=obj.sender.id).first()
        return f"{user.username}"

    def get_avatar(self, obj):
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

        temp = [f"{self.context['request'].user}", f"{receiver}"]
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
                "media": instance.media.url
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
        fields = ["id", "receiver", "media", "body", "created_at", "avatar", "channel", "unread_count"]

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

    def get_avatar(self, obj):
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

    def get_unread_count(self, obj):
        """
        The function `get_unread_count` returns the number of unread personal messages for a given user.

        :param obj: The `obj` parameter is not used in the code snippet provided. It seems to be unused
        and can be removed from the method signature
        :return: the count of unread personal messages for the specified user.
        """
        count = PersonalMessage.objects.filter(
            Q(sender=self.context['request'].user) | Q(receiver=self.context['request'].user), is_read=False).count()
        return count


__all__ = [
    "MessageSerializer",
    "MessageUpdateSerializer",
    "MessageCreateSerializer",
    "MessageListSerializer"
]
