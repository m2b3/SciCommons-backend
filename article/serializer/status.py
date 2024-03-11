# The `StatusSerializer` class is a serializer for the `Article` model that includes the `id` and
# `status` fields.
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'status']


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

    def update(self, instance, validated_data):
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
            raise serializers.ValidationError(
                detail={"error": f'article is not submitted for review {community_meta.community.Community_name}'})
        elif community_meta.status == "in review":
            raise serializers.ValidationError(detail={"error": f'article is already submitted for review'})
        elif community_meta.status == "accepted" or community_meta.status == "rejected":
            raise serializers.ValidationError(detail={"error": "article is already processed in this community"})

        authors = [User.id for User in Author.objects.filter(article=instance)]
        reviewers_arr = [reviewer for reviewer in
                         OfficialReviewer.objects.filter(community_id=community_data).exclude(User__in=authors)]
        moderators_arr = [moderator for moderator in
                          Moderator.objects.filter(community_id=community_data).exclude(user__in=authors)]

        if len(reviewers_arr) < 3:
            raise serializers.ValidationError(detail={"error": "Insufficient reviewers on Community"})

        if len(moderators_arr) == 0:
            raise serializers.ValidationError(detail={"error": "No Moderators on Community"})

        if len(reviewers_arr) >= 3:
            reviewers_arr = random.sample(reviewers_arr, 3)

        if len(moderators_arr) >= 1:
            moderators_arr = random.sample(moderators_arr, 1)

        community_meta.status = 'in review'
        community_meta.save()

        instance.reviewer.add(*[reviewer.id for reviewer in reviewers_arr])
        instance.moderator.add(*[moderator.id for moderator in moderators_arr])

        emails = [member.User.email for member in reviewers_arr]
        send_mail("New Article Alerts",
                  f'You have been added as an Official Reviewer to {instance.article_name} on {community_meta.community.Community_name}',
                  settings.EMAIL_HOST_USER, emails, fail_silently=False)

        emails = [member.user.email for member in moderators_arr]
        send_mail("New Article Alerts",
                  f'You have been added as a Moderator to {instance.article_name} on {community_meta.community.Community_name}',
                  settings.EMAIL_HOST_USER, emails, fail_silently=False)

        return {"status": community_meta.status, 'reviewers': instance.reviewer, 'moderator': instance.moderator}


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
        send_mail(f"Article is approved",
                  f"Your article: {instance.article_name} is approved by {communitymeta.community.Community_name}",
                  settings.EMAIL_HOST_USER, emails, fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user,
                                    action=f'you have approved the {instance.article_name} to {communitymeta.community.Community_name}')

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
        send_mail(f"Article is rejected",
                  f"Your article: {instance.article_name} is rejected by {communitymeta.community.Community_name}",
                  settings.EMAIL_HOST_USER, emails, fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user,
                                    action=f'you have rejected the {instance.article_name} to {communitymeta.community.Community_name}')

        return communitymeta