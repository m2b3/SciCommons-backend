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
        fields = ['id', 'article', 'Comment', 'Title', 'Type', 'rating', 'confidence', 'replies', 'role', 'blocked',
                  'tag', 'comment_type', 'user', 'Comment_date', 'commentrating', 'versions',
                  'parent_comment', 'rank', 'personal', 'userrating']

    def get_user(self, obj):
        """
        The function `get_user` returns the handle name of a user based on the given object.

        :param obj: The `obj` parameter is an object that contains the following attributes:
        :return: The handle_name of the first HandlersBase object that matches the User and article of
        the given obj.
        """
        handle = HandlersBase.objects.filter(User=obj.User, article=obj.article).first()
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

    def get_role(self, obj):
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
        elif (OfficialReviewer.objects.filter(User_id=obj.User_id).first() is not None) and (
                OfficialReviewer.objects.filter(User_id=obj.User_id).first().id in [reviewer.officialreviewer_id for
                                                                                    reviewer in
                                                                                    ArticleReviewer.objects.filter(
                                                                                        article=obj.article)]):
            return "reviewer"
        elif (Moderator.objects.filter(user_id=obj.User_id).first() is not None) and (
                Moderator.objects.filter(user_id=obj.User_id).first().id in [member.moderator_id for member in
                                                                             ArticleModerator.objects.filter(
                                                                                 article=obj.article)]):
            return "moderator"
        else:
            return "none"

    def get_blocked(self, obj):
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

    def get_replies(self, obj):
        """
        The function `get_replies` returns the number of replies to a given comment object.

        :param obj: The `obj` parameter is an object of the `CommentBase` model
        :return: The number of CommentBase objects that have a parent_comment equal to the given obj.
        """
        member = CommentBase.objects.filter(parent_comment=obj).count()
        return member

    def get_commentrating(self, obj):
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

    def get_userrating(self, obj):
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
        serializer = CommentSerializer(comment, many=True, context={'request': self.context['request']})
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
        fields = ['id', 'article', 'Comment', 'Title', 'Type', 'tag', 'comment_type', 'user', 'Comment_date',
                  'versions', 'role', 'blocked',
                  'parent_comment', 'rank', 'personal', 'replies', 'rating', 'confidence', 'version', 'commentrating',
                  'userrating']

    def get_user(self, obj):
        """
        The function `get_user` returns the handle name of a user based on the given object.

        :param obj: The `obj` parameter is an object that contains the following attributes:
        :return: The handle_name of the first HandlersBase object that matches the User and article of
        the given obj.
        """
        handle = HandlersBase.objects.filter(User=obj.User, article=obj.article).first()
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

    def get_blocked(self, obj):
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

    def get_role(self, obj):
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
        elif (OfficialReviewer.objects.filter(User_id=obj.User_id).first() is not None) and (
                OfficialReviewer.objects.filter(User_id=obj.User_id).first().id in [reviewer.officialreviewer_id for
                                                                                    reviewer in
                                                                                    ArticleReviewer.objects.filter(
                                                                                        article=obj.article)]):
            return "reviewer"
        elif (Moderator.objects.filter(user_id=obj.User_id).first() is not None) and (
                Moderator.objects.filter(user_id=obj.User_id).first().id in [member.moderator_id for member in
                                                                             ArticleModerator.objects.filter(
                                                                                 article=obj.article)]):
            return "moderator"
        else:
            return "none"

    def get_replies(self, obj):
        """
        The function `get_replies` returns the number of replies to a given comment object.

        :param obj: The `obj` parameter is an object of the `CommentBase` model
        :return: The number of CommentBase objects that have a parent_comment equal to the given obj.
        """
        member = CommentBase.objects.filter(parent_comment=obj).count()
        return member

    def get_commentrating(self, obj):
        """
        The function `get_commentrating` calculates the total rating of a post based on the sum of the
        values of all the likes associated with that post.

        :param obj: The "obj" parameter in the "get_commentrating" function is referring to the post
        object for which you want to calculate the rating
        :return: the sum of the values of all the likes associated with the given post object.
        """
        rating = LikeBase.objects.filter(post=obj).aggregate(Sum('value'))['value__sum']
        return rating

    def get_userrating(self, obj):
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
        serializer = CommentSerializer(comment, many=True, context={"request": self.context['request']})
        return serializer.data


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommentBase
        fields = ['id', 'article', 'Comment', 'Title', 'Type', 'tag', 'comment_type', 'parent_comment', 'rating',
                  'confidence', 'version']
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
        authors = [author for author in
                   Author.objects.filter(article=validated_data["article"], User=self.context["request"].user)]
        reviewers_arr = [reviewer for reviewer in ArticleReviewer.objects.filter(article=validated_data["article"],
                                                                                 officialreviewer__User=self.context[
                                                                                     "request"].user)]
        moderators_arr = [moderator for moderator in ArticleModerator.objects.filter(article=validated_data["article"],
                                                                                     moderator__user=self.context[
                                                                                         "request"].user)]

        if len(authors) > 0 or len(reviewers_arr) > 0 or len(moderators_arr) > 0:
            validated_data["comment_type"] = "OfficialComment"
        else:
            validated_data["comment_type"] = "PublicComment"
        instance = self.Meta.model.objects.create(**validated_data, User=self.context["request"].user)
        instance.save()

        handler = HandlersBase.objects.filter(User=instance.User, article=instance.article).first()

        if not handler:
            handler = HandlersBase.objects.create(User=instance.User, article=instance.article, handle_name=fake.name())
            handler.save()

        handler = HandlersBase.objects.filter(User=instance.User, article=instance.article).first()

        if validated_data["parent_comment"]:
            member = CommentBase.objects.filter(id=validated_data['parent_comment'].id).first()
            notification = Notification.objects.create(user=member.User,
                                                       message=f'{handler.handle_name} replied to your comment on {member.article.article_name} ',
                                                       link=f'/article/{member.article.id}/{instance.id}')
            notification.save()
            send_mail(f"somebody replied to your comment",
                      f"{handler.handle_name} have made a replied to your comment.\n {settings.BASE_URL}/article/{member.article.id}/{instance.id}",
                      settings.EMAIL_HOST_USER, [member.User.email], fail_silently=False)

        if validated_data["Type"] == "review" or validated_data["Type"] == "decision":
            emails = [author.User.email for author in authors]
            for author in authors:
                notification = Notification.objects.create(user=author.User,
                                                           message=f'{handler.handle_name} has added a {validated_data["Type"]} to your article: {instance.article.article_name} ',
                                                           link=f'/article/{instance.article.id}/{instance.id}')
                notification.save()
            send_mail(f"A new {validated_data['Type']} is added ",
                      f"{handler.handle_name} has added a {validated_data['Type']} to your article: {instance.article.article_name}. checkout this {settings.BASE_URL}/article/{instance.article.id}/{instance.id}",
                      settings.EMAIL_HOST_USER, emails, fail_silently=False)

        send_mail(f"you have made {instance.Type}",
                  f"You have made a {instance.Type} on {instance.article.article_name}. checkout this {settings.BASE_URL}/article/{instance.article.id}/{instance.id}",
                  settings.EMAIL_HOST_USER, [instance.User.email], fail_silently=False)
        UserActivity.objects.create(user=self.context['request'].user,
                                    action=f"You have made a {instance.Type} on {instance.article.article_name}")

        return instance


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommentBase
        fields = ['Comment', 'Title']


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LikeBase
        fields = ['post', 'value']
