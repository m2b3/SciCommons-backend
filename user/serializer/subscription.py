from rest_framework import serializers

from user.models import Subscribe, Notification, Favourite, UserActivity


# The SubscribeSerializer class is a serializer for the Subscribe model, with fields for id, user, and
# community, and the id field is read-only.
class SubscribeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscribe
        fields = ['id', 'user', 'community']
        read_only_fields = ['id']


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
            raise serializers.ValidationError({"error": "already in favourites"})

        instance = Favourite.objects.create(article=validated_data['article'],
                                            user=self.context['request'].user)
        instance.save()
        UserActivity.objects.create(
            user=self.context['request'].user,
            action=f"You added {instance.article.article_name} in favourite"
        )

        return instance


__all__ = [
    "SubscribeSerializer",
    "NotificationSerializer",
    "FavouriteSerializer",
    "FavouriteCreateSerializer",
]
