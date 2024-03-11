# The class ArticlePublishSelectionSerializer is a serializer class in Python that defines the fields
# to be included when serializing an Article model object.
class ArticlePublishSelectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'published', 'status']


# The above class is a serializer for the Article model that includes fields for the license,
# published article file, published date, and DOI.
class ArticlePostPublishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["license", "published_article_file", "published_date", "doi"]


class SubmitArticleSerializer(serializers.Serializer):
    communities = serializers.ListField(child=serializers.CharField(), write_only=True)
    meta_id = serializers.ListField(child=serializers.CharField(), read_only=True)
    article_id = serializers.CharField()

    class Meta:
        fields = ['article_id', 'communities', 'meta_id']

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
        if len(communities) == 0:
            raise serializers.ValidationError(detail={"error": "communities can't be empty or None"})

        if len(instance.link):
            raise serializers.ValidationError(detail={"error": "you can not submit external article"})

        with transaction.atomic():
            for community in communities:
                admin_users = CommunityMember.objects.filter(community_id=community, is_admin=True).values_list(
                    'user_id', flat=True)
                author_users = authors.values_list('User_id', flat=True)
                intersection_users = set(admin_users) & set(author_users)
                if len(intersection_users) > 0:
                    raise serializers.ValidationError(
                        detail={"error": "you can not submit article to community where you are admin!!!"})

                community_meta = CommunityMeta.objects.create(community_id=community, article=instance,
                                                              status='submitted')
                community_meta.save()

                community = Community.objects.get(id=community)

                emails = [member.user.email for member in CommunityMember.objects.filter(community=community)]
                send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}',
                          settings.EMAIL_HOST_USER, emails, fail_silently=False)
                meta_id.append(community_meta.id)

        return {"meta_id": meta_id}
