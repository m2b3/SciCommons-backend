from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, parsers, filters, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from article.filters import ArticleFilter
from article.models import Article, CommentBase
from article.permissions import ArticlePermission
from article.serializer.article import ArticleSerializer, ArticlelistSerializer, ArticleGetSerializer, \
    ArticleCreateSerializer, ArticleUpdateSerializer, ArticleViewsSerializer, ArticleBlockUserSerializer
from article.serializer.comment import CommentSerializer
from article.serializer.publish import SubmitArticleSerializer, ArticlePublishSelectionSerializer
from article.serializer.status import ApproveSerializer, InReviewSerializer, RejectSerializer, StatusSerializer
from community.models import CommunityMeta, Community
from community.serializer.meta import CommunityMetaApproveSerializer
from user.models import Favourite
from user.permissions import FavouritePermission
from user.serializer.subscription import FavouriteCreateSerializer, FavouriteSerializer


class ArticleViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling CRUD operations on the Article model. It
    # specifies the queryset to retrieve all Article objects, sets the permission classes to
    # ArticlePermission, and defines the parser classes for handling JSON, multipart, and form data.
    # It also specifies the serializer class to use for serializing and deserializing Article objects,
    # and sets the filter backends to DjangoFilterBackend, SearchFilter, and OrderingFilter for
    # filtering, searching, and ordering the queryset. The filterset_class is set to ArticleFilter for
    # more advanced filtering options. The allowed HTTP methods are specified as post, get
    queryset = Article.objects.all()
    permission_classes = [ArticlePermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = ArticleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, filters.OrderingFilter]
    filterset_class = ArticleFilter
    http_method_names = ['post', 'get', 'put', 'delete']
    search_fields = ['article_name', 'keywords', 'authorstring']

    action_serializers = {
        "list": ArticlelistSerializer,
        "retrieve": ArticleGetSerializer,
        "create": ArticleCreateSerializer,
        "approve_article": ApproveSerializer,
        "approve_review": InReviewSerializer,
        "reject_article": RejectSerializer,
        "submit_article": SubmitArticleSerializer,
        "update": ArticleUpdateSerializer,
        "getIsapproved": CommunityMetaApproveSerializer,
        "getPublished": ArticlePublishSelectionSerializer,
        "status": StatusSerializer,
        "updateViews": ArticleViewsSerializer,
        "block_user": ArticleBlockUserSerializer,
        "favourite": FavouriteCreateSerializer,
        "unfavourite": FavouriteSerializer,
        "favourites": FavouriteSerializer

    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_queryset(self):
        queryset = self.queryset
        return queryset

    def list(self, request):
        response = super(ArticleViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(ArticleViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):
        name = request.data['article_name']
        name = name.replace(' ', '_')
        article = self.queryset.filter(article_name=name).first()
        if article is not None:
            return Response(data={"error": "Article with same name already exists!!!"},
                            status=status.HTTP_400_BAD_REQUEST)
        response = super(ArticleViewset, self).create(request)

        # send the response as a JSON object with a "success" key and the serialized data of the article
        return Response(data={"success": response.data})

    def update(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        article = Article.objects.filter(id=pk).first()
        response = ArticleGetSerializer(article, context={'request': request})
        return Response(data={"success": "Article successfully updated", "data": response.data})

    def destroy(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)

        super(ArticleViewset, self).destroy(request, pk=pk)

        return Response(data={"success": "Article successfully deleted"})

    @action(methods=['get'], detail=True, url_path='comment/(?P<comment_id>.+)', permission_classes=[ArticlePermission])
    def retrieve_comment(self, request, pk, article_id=None, comment_id=None):
        # Fetch the first comment with the given ID
        comment = CommentBase.objects.filter(article=pk, id=comment_id).first()
        if comment:
            # If the comment exists, serialize it and return it in the response
            # Pass the request context to the serializer
            serializer = CommentSerializer(comment, context={"request": request})
            return Response(serializer.data)
        else:
            # If the comment does not exist, return a 404 Not Found response
            return Response(status=404)

    @action(methods=['get'], detail=False, url_path='(?P<pk>.+)/isapproved', permission_classes=[ArticlePermission])
    def getIsapproved(self, request, pk):
        """
        This function retrieves the status of an article in different communities with an accepted
        status.

        :param request: The request object contains information about the current HTTP request, such as
        the user making the request, the headers, and the request method
        :param pk: The `pk` parameter in the `getIsapproved` method represents the primary key of the
        article for which you want to retrieve the status in different communities with an accepted
        status
        :return: The response is a JSON object containing the success status and the communities where
        the article has been approved.
        """

        # Retrieve the article object from the database
        obj = self.get_object()
        # Check if the user has permission to access the article
        self.check_object_permissions(request, obj)
        response = CommunityMeta.objects.filter(article_id=pk)
        serializer = CommunityMetaApproveSerializer(data=response, many=True)
        serializer.is_valid()
        communities = serializer.data
        return Response(data={"success": communities})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/approve_for_review',
            permission_classes=[ArticlePermission])
    def approve_review(self, request, pk):
        """
        This function approves an article for the review process.

        :param request: The request object contains information about the HTTP request made to the API,
        such as the request method (POST in this case), headers, and body
        :param pk: The "pk" parameter in the URL pattern is used to capture the primary key of the
        article that needs to be approved for review. It is a placeholder that will be replaced with the
        actual primary key value when the URL is accessed
        :return: The code is returning a response with a success message indicating that the review
        process has started successfully.
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data={"success": "review process started successfully"})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/publish', permission_classes=[ArticlePermission])
    def getPublished(self, request, pk):
        """
        This function selects a community for publication and updates the status of the article
        accordingly.

        :param request: The request object contains information about the current HTTP request, such as
        the headers, body, and user authentication details
        :param pk: The `pk` parameter is a placeholder for the primary key of the article. It is used to
        identify the specific article that is being published
        :return: The code is returning a response in the form of a JSON object. The specific content of
        the response depends on the conditions met in the code.
        """
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        data = request.data
        response = CommunityMeta.objects.filter(article_id=pk, community__Community_name=data["published"]).first()
        if response is None:
            return Response(data={"error": f'Article is not submitted to {data["published"]}'})
        if response.status == 'accepted':
            article = Article.objects.filter(id=pk).first()
            article.published = data['published']
            article.save()
            response.status = data['status']
            response.save()
            return Response(data={"success": f"You have chosen {data['Community_name']} to publish your article"})
        else:
            return Response(data={"error": "Article is still not approved by community"})

    @action(methods=['get'], detail=False, url_path='favourites', permission_classes=[ArticlePermission])
    def favourites(self, request):
        """
        The above function retrieves a list of articles that have been marked as favorites by the user
        and returns them in a serialized format.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the user making the request, the HTTP method used
        (GET, POST, etc.), and any data or parameters sent with the request
        :return: The code is returning a response with a JSON object containing the serialized data of
        the articles that are marked as favourites by the authenticated user. The serialized data
        includes the details of the articles such as title, content, author, etc.
        """
        favourites = Favourite.objects.filter(user=request.user).values_list('article', flat=True)
        posts = Article.objects.filter(id__in=favourites.all(), status="public")
        serializer = ArticlelistSerializer(posts, many=True, context={"request": request})
        return Response(data={"success": serializer.data})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/submit_article',
            permission_classes=[ArticlePermission])
    def submit_article(self, request, pk):
        """
        This function submits an article to different communities for reviewal process.

        :param request: The request object contains information about the current HTTP request, such as
        the request method, headers, and data
        :param pk: The `pk` parameter in the `submit_article` method represents the primary key of the
        object that the article is being submitted to. It is used to retrieve the object from the
        database and perform permission checks on it
        :return: The code is returning a response with a JSON object containing the key "success" and
        the value "Article submitted successfully for reviewal process!!!".
        """
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        data = request.data
        data['article_id'] = pk
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data={"success": "Article submited successfully for reviewal process!!!"})

    @action(methods=['put'], detail=False, url_path='(?P<pk>.+)/updateviews', permission_classes=[ArticlePermission])
    def updateViews(self, request, pk):
        """
        This function updates the number of views for an article.

        :param request: The `request` parameter is the HTTP request object that contains information
        about the current request, such as the headers, body, and user authentication details. It is
        passed to the view function or method when a request is made to the corresponding URL
        :param pk: The "pk" parameter in the above code refers to the primary key of the article object
        that needs to be updated. It is used to identify the specific article that needs to have its
        views incremented
        :return: The code is returning a response with a success message if the serializer is valid and
        the view count is successfully updated. If the serializer is not valid, it returns a response
        with the serializer errors and a status of HTTP 400 Bad Request.
        """
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = self.queryset.get(id=pk)
        serializer = ArticleViewsSerializer(response)
        article = serializer.data
        article['views'] += 1
        serializer = ArticleViewsSerializer(response, data=article)
        if serializer.is_valid():
            serializer.save()
            return Response(data={"success": "Added a view to the article"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/approve_article',
            permission_classes=[ArticlePermission])
    def approve_article(self, request, pk):
        """
        This function is used by an admin to approve an article and select reviewers and moderators for
        a community.

        :param request: The request object contains information about the HTTP request made by the
        client, such as the headers, body, and method
        :param pk: The "pk" parameter is a regular expression pattern that matches any string of
        characters. It is used to capture the primary key (pk) of the article that needs to be approved
        :return: The response being returned is a JSON object with a "success" key and the value
        "article approved".
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data={"success": "article approved"})

    @action(methods=['post'], detail=False, url_path="favourite", permission_classes=[FavouritePermission])
    def favourite(self, request):
        """
        This function adds an article to a user's list of favorites if it is not already added.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this code snippet, the `request` object is used to access
        the data sent
        :return: The code is returning a Response object with data indicating whether the favourite was
        successfully added or if it was already added to favourites. If the favourite was already added,
        the response will contain an error message. If the favourite was successfully added, the
        response will contain a success message.
        """
        post = Favourite.objects.filter(article_id=request.data["article"], user=request.user).first()
        if post is not None:
            return Response(data={"error": "Already added to Favourites!!!"})
        Favourite.objects.create(article_id=request.data["article"], user=request.user)
        return Response(data={"success": "Favourite added!!!"})

    @action(methods=['post'], detail=False, url_path="unfavourite", permission_classes=[FavouritePermission])
    def unfavourite(self, request):
        """
        The above function is a Django view that allows a user to unfavourite an article.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this case, it is used to retrieve the data from the request
        body, specifically
        :return: The code is returning a Response object with either a success message ("Favourite
        Removed!!!") or an error message ("Favourite not found!!!").
        """
        member = Favourite.objects.filter(article_id=request.data["article"], user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "Favourite Removed!!!"})
        else:
            return Response(data={"error": "Favourite not found!!!"})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/reject_article',
            permission_classes=[ArticlePermission])
    def reject_article(self, request, pk):
        """
        This function rejects an article by updating its status and returning a success message.

        :param request: The request object contains information about the HTTP request made by the
        client, such as the headers, body, and method
        :param pk: The `pk` parameter in the `reject_article` method represents the primary key of the
        article that is being rejected. It is used to identify the specific article that needs to be
        rejected
        :return: The response being returned is a JSON object with the key "success" and the value
        "article rejected".
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data={"success": "article rejected"})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/status', permission_classes=[ArticlePermission])
    def status(self, request, pk):
        """
        This function updates the status of an article based on the provided status value.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body
        :param pk: The "pk" parameter in the above code refers to the primary key of the article object.
        It is used to identify a specific article in the database
        :return: The code is returning a response object with the data and status code. If the "status"
        parameter is not provided in the request data, it will return a response with an error message
        and status code 400 (Bad Request). If the article with the given ID does not exist, it will
        return a response with an error message and status code 404 (Not Found). If the article status
        is
        """
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        try:
            stat = request.data.get("status", None)
            if stat is None:
                return Response(data={"error": "status can't be None"}, status=status.HTTP_400_BAD_REQUEST)

            article = Article.objects.filter(id=pk).first()
            if article is None:
                return Response(data={"error": "article not exist"}, status=status.HTTP_404_NOT_FOUND)
            article.status = stat
            article.save()
            return Response(data={"success": f"article status changed to {stat}"})

        except Exception as e:
            return Response(data={"error": e}, status=status.HTTP_400_BAD_REQUEST)
