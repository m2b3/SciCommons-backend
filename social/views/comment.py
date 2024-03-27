from rest_framework import viewsets, parsers
from rest_framework.decorators import action
from rest_framework.response import Response

from social.models import SocialPostComment, SocialPostCommentLike
from social.permissions import SocialPostCommentPermission
from social.serializer import SocialPostCommentSerializer, SocialPostCommentCreateSerializer, \
    SocialPostCommentListSerializer, SocialPostCommentUpdateSerializer, SocialPostCommentLikeSerializer


class SocialPostCommentViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling social post comments. It is using the
    # `SocialPostComment` model as the queryset for retrieving comments. The view has specified the
    # `SocialPostCommentPermission` class as the permission class, which determines who can access the
    # view. It is also using various parser classes to parse the incoming request data.
    queryset = SocialPostComment.objects.all()
    permission_classes = [SocialPostCommentPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = SocialPostCommentSerializer
    http_method_names = ['get', 'post', 'delete', 'put']

    action_serializers = {
        "create": SocialPostCommentCreateSerializer,
        "destroy": SocialPostCommentSerializer,
        "retrieve": SocialPostCommentListSerializer,
        "list": SocialPostCommentListSerializer,
        "update": SocialPostCommentUpdateSerializer,
        "like": SocialPostCommentLikeSerializer,
        "unlike": SocialPostCommentLikeSerializer
    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_queryset(self):
        # The above code is a Python function that filters a queryset based on the values of the
        # "post" and "comment" query parameters.
        post = self.request.query_params.get("post", None)
        comment = self.request.query_params.get("comment", None)
        if comment is not None:
            qs = self.queryset.filter(post_id=post, parent_comment_id=comment)
        elif post is not None:
            qs = self.queryset.filter(post_id=post).exclude(parent_comment__isnull=False)
        else:
            qs = []
        return qs

    def list(self, request):
        response = super(SocialPostCommentViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(SocialPostCommentViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):
        response = super(SocialPostCommentViewset, self).create(request)
        created = response.data

        return Response(data={"success": "Comment Successfully added!!!", "comment": created})

    def update(self, request, pk):

        instance = SocialPostComment.objects.filter(id=pk).first()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(SocialPostCommentViewset, self).destroy(request, pk)

        return Response(data={"success": "Comment Successfuly removed!!!"})

    @action(methods=['post'], detail=False, url_path="like", permission_classes=[SocialPostCommentPermission])
    def like(self, request):
        """
        The above function allows a user to like a social post comment, but returns an error message if
        the user has already liked the comment.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this case, it is used to retrieve the data sent in the
        request body,
        :return: The response being returned is a JSON object with either an "error" key and value if
        the comment has already been liked, or a "success" key and value if the like is successfully
        created.
        """
        if SocialPostCommentLike.objects.filter(comment_id=request.data["comment"],
                                                user=request.user).first() is not None:
            return Response(data={"error": "Already Liked!!!"})
        SocialPostCommentLike.objects.create(comment_id=request.data["comment"], user=request.user)
        return Response(data={"success": "Liked!!!"})

    @action(methods=['post'], detail=False, url_path="unlike", permission_classes=[SocialPostCommentPermission])
    def unlike(self, request):
        """
        The above function allows a user to unlike a comment on a social post.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, user
        authentication details, and the request data (e.g., form data, JSON payload). In this case, the
        `
        :return: The code is returning a response in JSON format. If the comment is found and
        successfully deleted, it will return a success message: {"success": "DisLiked!!!"}. If the
        comment is not found, it will return an error message: {"error": "Comment not found!!!"}.
        """
        comment = SocialPostCommentLike.objects.filter(comment_id=request.data["comment"], user=request.user).first()
        if comment is not None:
            comment.delete()
            return Response(data={"success": "DisLiked!!!"})
        else:
            return Response(data={"error": "Comment not found!!!"})