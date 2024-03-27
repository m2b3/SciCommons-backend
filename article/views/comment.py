from django_filters.rest_framework import DjangoFilterBackend
from faker import Faker
from rest_framework import viewsets, parsers, filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from article.filters import CommentFilter
from article.models import CommentBase, LikeBase, ArticleBlockedUser, HandlersBase, ArticleModerator, Article, Author
from article.permissions import CommentPermission
from article.serializer import CommentSerializer, CommentlistSerializer, CommentCreateSerializer, \
    CommentUpdateSerializer, CommentParentSerializer, ArticleBlockUserSerializer, LikeSerializer, \
    CommentNestedSerializer
from community.models import Community, CommunityMeta
from user.models import Rank

faker = Faker()


class CommentViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling comments. It retrieves all instances of
    # the CommentBase model from the database using the `objects.all()` method and assigns it to the
    # `queryset` variable. It also retrieves all instances of the LikeBase model and assigns it to the
    # `queryset2` variable.
    queryset = CommentBase.objects.all()
    queryset2 = LikeBase.objects.all()
    permission_classes = [CommentPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CommentFilter
    http_method_names = ['post', 'get', 'put', 'delete']

    action_serializer = {
        "list": CommentlistSerializer,
        "create": CommentCreateSerializer,
        "update": CommentUpdateSerializer,
        "retrieve": CommentSerializer,
        "destroy": CommentSerializer,
        "like": LikeSerializer,
        "parents": CommentParentSerializer,
        "block_user": ArticleBlockUserSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializer.get(self.action, self.serializer_class)

    def get_queryset(self):
        """
        The `get_queryset` function filters the queryset based on various query parameters.
        :return: a queryset based on the provided query parameters. If the "article" parameter is not
        provided, an empty queryset is returned. Otherwise, the queryset is filtered based on the provided
        parameters (article, tag, Type, comment_type, parent_comment, and version).
        """
        article = self.request.query_params.get("article", None)
        tag = self.request.query_params.get("Community_name", None)
        Type = self.request.query_params.get("Type", None)
        comment_type = self.request.query_params.get("comment_type", None)
        parent_comment = self.request.query_params.get("parent_comment", None)
        version = self.request.query_params.get("version", None)
        if article is not None:
            if Type is not None:
                if tag is not None:
                    if comment_type is not None:
                        qs = self.queryset.filter(article=article, tag=tag, Type=Type, comment_type=comment_type,
                                                  parent_comment=parent_comment, version=version)
                    else:
                        qs = self.queryset.filter(article=article, tag=tag, Type=Type, parent_comment=parent_comment,
                                                  version=version)
                else:
                    if comment_type is not None:
                        qs = self.queryset.filter(article=article, Type=Type, comment_type=comment_type,
                                                  parent_comment=parent_comment, version=version)
                    else:
                        qs = self.queryset.filter(article=article, Type=Type, parent_comment=parent_comment,
                                                  version=version)
            else:
                if tag is not None:
                    if comment_type is not None:
                        qs = self.queryset.filter(article=article, tag=tag, comment_type=comment_type,
                                                  parent_comment=parent_comment, version=version)
                    else:
                        qs = self.queryset.filter(article=article, tag=tag, parent_comment=parent_comment,
                                                  version=version)
                else:
                    if comment_type is not None:
                        qs = self.queryset.filter(article=article, comment_type=comment_type,
                                                  parent_comment=parent_comment, version=version)
                    else:
                        qs = self.queryset.filter(article_id=article, parent_comment=parent_comment, version=version)
        else:
            qs = CommentBase.objects.none()

        return qs

    def list(self, request):

        response = super(CommentViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):

        response = super(CommentViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):
        """
        The `create` function checks various conditions and creates a comment, decision, or review based on
        the request data.

        :param request: The `request` parameter is an object that contains information about the HTTP
        request made by the client. It includes details such as the request method (GET, POST, etc.),
        headers, body, and user information. In this code snippet, the `request` object is used to access
        data sent in
        :return: The code returns a response object with different data depending on the conditions in the
        code. The possible responses are:
        """
        member = ArticleBlockedUser.objects.filter(article=request.data["article"], user=request.user).first()
        if member is not None:
            return Response(data={"error": "You are blocked from commenting on this article by article moderator!!!"},
                            status=status.HTTP_400_BAD_REQUEST)
        if request.data["parent_comment"] or request.data["version"]:
            request.data["Type"] = "comment"

        if request.data["Type"] == 'decision':
            moderators_arr = [moderator for moderator in
                              ArticleModerator.objects.filter(article=request.data["article"],
                                                              moderator__user=request.user)]
            if len(moderators_arr) > 0:
                if self.queryset.filter(article=request.data["article"], User=request.user, Type="decision").first():
                    return Response(data={"error": "You have already made decision!!!"},
                                    status=status.HTTP_400_BAD_REQUEST)
                else:
                    decision = request.data["decision"]
                    request.data.pop("decision")
                    communityName = request.data["tag"]
                    community = Community.objects.filter(Community_name=communityName).first()
                    member = CommunityMeta.objects.filter(article=request.data["article"],
                                                          community_id=community.id).first()
                    member.status = decision
                    member.save()
                    response = super(CommentViewset, self).create(request)
                    member = CommentBase.objects.filter(id=response.data.get("id")).first()
                    created = CommentSerializer(instance=member, context={'request': request})
                    return Response(data={"success": "Decision successfully added", "comment": created.data})

            else:
                return Response(data={"error": "You can't write a decision on the article!!!"},
                                status=status.HTTP_400_BAD_REQUEST)

        elif request.data['Type'] == 'review':
            author = Author.objects.filter(User=request.user, article=request.data["article"]).first()
            if author is not None:
                return Response(data={"error": "You are Author of Article.You can't submit a review"},
                                status=status.HTTP_400_BAD_REQUEST)

            c = ArticleModerator.objects.filter(article=request.data["article"], moderator__user=request.user).count()
            if c > 0:
                return Response(data={"error": "You can't make a review over article"},
                                status=status.HTTP_400_BAD_REQUEST)

            count = CommentBase.objects.filter(article=request.data["article"], User=request.user,
                                               tag=request.data['tag'], Type='review').count()
            if count == 0:
                response = super(CommentViewset, self).create(request)
                member = CommentBase.objects.filter(id=response.data.get("id")).first()
                created = CommentSerializer(instance=member, context={'request': request})
                return Response(data={"success": "Review successfully added", "comment": created.data})

            else:
                return Response(data={"error": "Review already added by you!!!"}, status=status.HTTP_400_BAD_REQUEST)

        else:
            if request.data['Type'] == 'comment' and (
                    request.data['parent_comment'] or request.data['version']) is None:
                return Response(data={"error": "Comment must have a parent instance"},
                                status=status.HTTP_400_BAD_REQUEST)

            response = super(CommentViewset, self).create(request)
            member = CommentBase.objects.filter(id=response.data.get("id")).first()
            created = CommentSerializer(instance=member, context={'request': request})
            return Response(data={"success": "Comment successfully added", "comment": created.data})

    def update(self, request, pk):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):
        member = CommentBase.objects.filter(id=pk).first()
        if member is None:
            return Response(data={"error": "Comment not found!!!"}, status=status.HTTP_404_NOT_FOUND)
        member.delete()
        return Response(data={"success": "Comment successfully deleted"})

    @action(methods=['post'], detail=False, permission_classes=[permissions.IsAuthenticated])
    def like(self, request):
        """
        This function allows authenticated users to like or rate a comment, updating the rank of the
        comment's user and the overall rank of the comment.

        :param request: The `request` parameter is an object that represents the HTTP request made by the
        client. It contains information such as the request method (e.g., POST), headers, user
        authentication details, and the data sent in the request body. In this code snippet, the `request`
        object is used to
        :return: The code is returning a response in the form of a JSON object. If the condition `if member
        is not None` is true, it returns a success message "Comment rated successfully." If the condition is
        false, it creates a new `LikeBase` object, updates the rank of the comment's user, and returns the
        success message "Comment rated successfully."
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = LikeBase.objects.filter(user=request.user, post=serializer.data['post']).first()
        comment = CommentBase.objects.filter(id=serializer.data['post']).first()
        if comment.User == request.user:
            return Response(data={'error': "you can't rate your comment"}, status=status.HTTP_400_BAD_REQUEST)
        handle = HandlersBase.objects.filter(User=request.user, article=comment.article).first()
        if handle is None:
            handle = HandlersBase.objects.create(User=request.user, article=comment.article, handle_name=faker.name())
            handle.save()
        handle = HandlersBase.objects.filter(User=self.request.user, article=comment.article).first()
        if member is not None:
            rank = Rank.objects.filter(user=comment.User).first()
            rank.rank -= member.value
            rank.rank += serializer.data['value']
            member.value = serializer.data['value']
            member.save()
            rank.save()
            return Response({'success': 'Comment rated successfully.'})
        else:

            like = LikeBase.objects.create(user=self.request.user, post=comment, value=serializer.data['value'])
            like.save()

            rank = Rank.objects.filter(user=comment.User).first()
            if rank:
                rank.rank += serializer.data['value']
                rank.save()

            else:
                rank = Rank.objects.create(user=self.request.user, rank=serializer.data['value'])
                rank.save()

            return Response({'success': 'Comment rated successfully.'})

    @action(methods=['get'], detail=False, url_path='(?P<pk>.+)/parents',
            permission_classes=[permissions.IsAuthenticated, ])
    def parents(self, request, pk):
        """
        This function retrieves the parent comments of a given comment.

        :param request: The `request` parameter is an object that represents the HTTP request made by the
        client. It contains information such as the request method (e.g., GET, POST), headers, and any data
        sent with the request
        :param pk: The "pk" parameter in the above code refers to the primary key of the comment object. It
        is used to identify the specific comment for which the parent comments need to be retrieved
        :return: The code is returning a response in the form of a JSON object. The response contains the
        serialized data of the parent comments of the given comment. The serialized data includes details
        such as the content, author, and date of the parent comments.
        """
        print("swaroop", pk)
        comment = pk
        while True:
            member = CommentBase.objects.filter(id=comment).first()
            if member.parent_comment is None:
                break
            comment = member.parent_comment.id
        response = CommentBase.objects.filter(id=comment).first()
        serializer = CommentNestedSerializer(response, context={'request': request})
        return Response(data={"success": serializer.data})

    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/block_user', permission_classes=[CommentPermission])
    def block_user(self, request, pk):
        """
        The above function blocks a user from accessing an article.

        :param request: The request object contains information about the current HTTP request, such as
        the headers, body, and user authentication details
        :param pk: The "pk" parameter in the above code refers to the primary key of the article object.
        It is used to identify the specific article that the user wants to block a user from
        :return: The code is returning a response in JSON format. If the user is already blocked, it
        will return a response with an error message: {"error": "User already blocked!!!"}. If the user
        is successfully blocked, it will return a response with a success message: {"success": "user
        blocked successfully"}.
        """
        comment = CommentBase.objects.filter(id=pk).first()
        member = ArticleBlockedUser.objects.filter(article=comment.article, user=comment.User).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "User is unblocked successfully!!!"})
        ArticleBlockedUser.objects.create(article=comment.article, user=comment.User)
        return Response(data={"success": f"user blocked successfully!!!"})
