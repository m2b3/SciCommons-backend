from rest_framework import serializers

from article.models import Article
from chat.models import ArticleMessage
from user.models import User

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

    def get_personal(self, obj):
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
        fields = ["id", "body", "article"]
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


__all__ = [
    "ArticleChatSerializer",
    "ArticleChatUpdateSerializer",
    "ArticleChatCreateSerializer",
]
