import json
import uuid

from django.db import transaction
from rest_framework import serializers

from article.models import Author, Article, CommentBase, ArticleReviewer, ArticleModerator
from community.models import CommunityMember, Community, CommunityMeta, UnregisteredUser
from user.models import UserActivity, User, Favourite


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
        rating = CommentBase.objects.filter(article_id=obj.id, Type='review').aggregate(Avg('rating'))['rating__avg']
        return rating


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
        fields = ['id', 'article_name', 'Public_date', 'views', 'authors', 'rating', 'isFavourite', 'keywords',
                  'favourites', 'unregistered_authors']

    def get_rating(self, obj):
        """
        The function `get_rating` calculates the average rating of comments with the type 'review' for a
        given article.

        :param obj: The "obj" parameter is an object that represents an article
        :return: the average rating of comments that have a type of 'review' for a given article object.
        """
        rating = CommentBase.objects.filter(article_id=obj.id, Type='review').aggregate(Avg('rating'))['rating__avg']
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
        elif (Favourite.objects.filter(article=obj.id, user=self.context['request'].user).count() > 0):
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

    def get_unregistered_authors(self, obj):
        """
        The function "get_unregistered_authors" returns a list of dictionaries containing the full name
        and email of unregistered users associated with a given article.

        :param obj: The "obj" parameter is an instance of an article object
        :return: a list of dictionaries, where each dictionary represents an unregistered author
        associated with the given article object. Each dictionary contains the full name and email of
        the author.
        """
        unregistered = UnregisteredUser.objects.filter(article=obj.id)
        authors = [{'fullName': user.fullName, 'email': user.email} for user in unregistered]
        return authors


class ArticleGetSerializer(serializers.ModelSerializer):
    versions = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    isArticleReviewer = serializers.SerializerMethodField()
    isArticleModerator = serializers.SerializerMethodField()
    isFavourite = serializers.SerializerMethodField()
    isAuthor = serializers.SerializerMethodField()
    userRating = serializers.SerializerMethodField()
    commentCount = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    unregistered_authors = serializers.SerializerMethodField()
    article_file = serializers.SerializerMethodField()
    favourites = serializers.SerializerMethodField()
    published_article_file = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ['id', 'article_name', 'article_file', 'Public_date', 'Code', 'Abstract', 'views', 'video', 'doi',
                  'published_article_file',
                  'link', 'authors', 'rating', 'versions', 'isArticleReviewer', 'isArticleModerator', 'isAuthor',
                  'status',
                  'isFavourite', 'userrating', 'commentcount', 'favourites', 'license', 'published_date', 'published',
                  'unregistered_authors']

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
            serialized_child_articles = ArticleGetSerializer(obj.versions.all(), many=True)
            return serialized_child_articles.data

        else:
            child_articles = Article.objects.exclude(id=obj.id).filter(parent_article=obj.parent_article)
            serialized_child_articles = ArticleGetSerializer(child_articles, many=True)
            return serialized_child_articles.data

    def get_article_file(self, obj):
        if obj.article_file:
            url = obj.article_file.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'

    def get_published_article_file(self, obj):
        if obj.published_article_file:
            url = obj.published_article_file.url.split('?')[0]
            return url
        return 'https://scicommons.s3.amazonaws.com/None'

    def get_commentCount(self, obj):
        """
        The function `get_commentCount` returns the count of top-level comments for a given article.

        :param obj: The `obj` parameter is an object that represents an article
        :return: the count of comments that meet the specified criteria.
        """
        count = CommentBase.objects.filter(article_id=obj.id, parent_comment=None, version=None).count()
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
        rating = CommentBase.objects.filter(article_id=obj.id, Type='review').aggregate(Avg('rating'))['rating__avg']
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
        if ArticleReviewer.objects.filter(
                article=obj.id,
                officialreviewer__User_id=self.context['request'].user
        ).exists():
            return True
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
        if ArticleModerator.objects.filter(
                article=obj.id,
                moderator__user_id=self.context['request'].user
        ).exists():
            return True
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
        if (Author.objects.filter(article=obj.id, User=self.context['request'].user).count() > 0):
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
        elif Favourite.objects.filter(article=obj.id, user=self.context['request'].user).exists():
            return True
        return False

    def get_userRating(self, obj):
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
        rating = CommentBase.objects.filter(article_id=obj.id, Type='review', User=self.context['request'].user).first()
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

    def get_unregistered_authors(self, obj):
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
        authors = [{'fullName': user.fullName} for user in unregistered]
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


# The class `ArticleUpdateSerializer` is a serializer for updating an `Article` model and includes
# fields for `article_file`, `Code`, `Abstract`, `video`, `link`, and `status`.
class ArticleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['article_file', 'Code', 'Abstract', 'video', 'link', 'status']


class ArticleCreateSerializer(serializers.ModelSerializer):
    authors = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    communities = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    unregistered_authors = serializers.ListField(child=serializers.CharField(), write_only=True)

    class Meta:
        model = Article
        fields = ['id', 'article_name', 'keywords', 'article_file', 'Code', 'Abstract', 'authors', 'video', 'link',
                  'parent_article', 'communities', 'unregistered_authors']
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
            keywords.replace(' ', '_')
            validated_data['article_name'] = name.replace(' ', '_')
            validated_data['keywords'] = keywords
            instance = self.Meta.model.objects.create(**validated_data, id=uuid.uuid4().hex)
            Author.objects.create(User=self.context['request'].user, article=instance)
            authorstr = ""
            authorstr += self.context['request'].user.first_name + '_' + self.context['request'].user.last_name + "_" + \
                         self.context['request'].user.username + "||"
            if len(unregistered_authors) != 0:
                with transaction.atomic():
                    for author in unregistered_authors:
                        data = json.loads(author)
                        user = User.objects.filter(email=data["email"]).first()
                        if user is not None:
                            Author.objects.create(User=user, article=instance)
                            authorstr += author.User.first_name + '_' + author.User.last_name + "_" + author.username + "||"
                        else:
                            UnregisteredUser.objects.create(email=data["email"], article=instance,
                                                            fullName=data["fullName"])
                            authorstr += data["fullName"] + "||"
                        # send_mail("Article added", f"You have added an article {instance.article_name} to SciCommons",
                        #           settings.EMAIL_HOST_USER, [data["email"]], fail_silently=False)

            if len(authors) != 0:
                with transaction.atomic():
                    for author in authors:
                        author = Author.objects.create(User_id=author, article=instance)
                        authorstr += author.User.first_name + '_' + author.User.last_name + "_" + author.username + "||"
                        # send_mail("Article added", f"You have added an article {instance.article_name} to SciCommons",
                        #           settings.EMAIL_HOST_USER, [author.User.email], fail_silently=False)
                        UserActivity.objects.create(user=self.context['request'].user,
                                                    action=f'you added article {instance.article_name}')
            instance.authorstring = authorstr
            if len(communities) > 0 and instance.link is not None:
                raise serializers.ValidationError(detail={"error": "you can not submit external article"})

            if len(communities) > 0:
                with transaction.atomic():
                    for community in communities:
                        community_meta = CommunityMeta.objects.create(community_id=community, article=instance,
                                                                      status='submitted')
                        community_meta.save()

                        community = Community.objects.filter(id=community).first()

                        emails = [member.user.email for member in
                                  CommunityMember.objects.filter(community_id=community)]
                        # send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}',
                        #           settings.EMAIL_HOST_USER, emails, fail_silently=False)
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
            keywords.replace(' ', '_')
            validated_data['article_name'] = name.replace(' ', '_')
            validated_data['keywords'] = keywords
            instance = self.Meta.model.objects.create(**validated_data, id=uuid.uuid4().hex)
            Author.objects.create(User=self.context['request'].user, article=instance)
            authorstr = ""
            authorstr += self.context['request'].user.first_name + '_' + self.context['request'].user.last_name + "_" + \
                         self.context['request'].user.username + "||"
            if len(unregistered_authors) != 0:
                with transaction.atomic():
                    for author in unregistered_authors:
                        data = json.loads(author)
                        user = User.objects.filter(email=data["email"]).first()
                        if user is not None:
                            Author.objects.create(User=user, article=instance)
                            authorstr += author.User.first_name + '_' + author.User.last_name + "_" + author.username + "||"
                        else:
                            UnregisteredUser.objects.create(email=data["email"], article=instance,
                                                            fullName=data["fullName"])
                            authorstr += data["fullName"] + "||"
                        # send_mail("Article added", f"You have added an article {instance.article_name} to SciCommons",
                        #           settings.EMAIL_HOST_USER, [data["email"]], fail_silently=False)

            if len(authors) != 0:
                with transaction.atomic():
                    for author in authors:
                        author = Author.objects.create(User_id=author, article=instance)
                        authorstr += author.User.first_name + '_' + author.User.last_name + "_" + author.username + "||"
                        # send_mail("Article added", f"You have added an article {instance.article_name} to SciCommons",
                        #           settings.EMAIL_HOST_USER, [author.User.email], fail_silently=False)
                        UserActivity.objects.create(user=self.context['request'].user,
                                                    action=f'you added article {instance.article_name}')
            instance.authorstring = authorstr
            communities = [community for community in parentinstance.communities]
            instance.communities.set(communities)
            instance.parent_article = parent_article

            with transaction.atomic():
                for community in communities:
                    community_meta = CommunityMeta.objects.create(community_id=community, article=instance,
                                                                  status='submitted')
                    community_meta.save()

                    community = Community.objects.get(id=community)

                    emails = [member.user.email for member in CommunityMember.objects.filter(community=community)]
                    # send_mail("New Article Alerts", f'New Article {instance.article_name} added on {community}',
                    #           settings.EMAIL_HOST_USER, emails, fail_silently=False)
            instance.save()
            return instance


'''
AuthorSerializer
'''


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['article']
        depth = 1
