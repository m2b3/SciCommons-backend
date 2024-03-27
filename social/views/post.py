from django_filters.rest_framework import DjangoFilterBackend, filters
from rest_framework import viewsets, parsers
from rest_framework.decorators import action
from rest_framework.response import Response

from social.filters import PostFilters
from social.models import SocialPost, Follow, Bookmark, SocialPostLike
from social.permissions import SocialPostPermission
from social.serializer import (
    SocialPostSerializer,
    SocialPostCreateSerializer,
    SocialPostGetSerializer,
    SocialPostListSerializer,
    SocialPostUpdateSerializer,
    SocialPostLikeSerializer,
    SocialPostBookmarkSerializer,
)


class SocialPostViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling social posts. It is using the `SocialPost`
    # model as the queryset, applying the `SocialPostPermission` class for permission checks, and
    # using various parsers for handling different types of data (JSON, multipart, form). It is also
    # using the `SocialPostSerializer` class for serialization, and applying the `PostFilters` class
    # for filtering the queryset. The allowed HTTP methods for this view are GET, POST, DELETE, and
    # PUT.
    queryset = SocialPost.objects.all()
    permission_classes = [SocialPostPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = SocialPostSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = PostFilters
    http_method_names = ['get', 'post', 'delete', 'put']

    action_serializers = {
        "create": SocialPostCreateSerializer,
        "destroy": SocialPostSerializer,
        "retrieve": SocialPostGetSerializer,
        "list": SocialPostListSerializer,
        "update": SocialPostUpdateSerializer,
        "like": SocialPostLikeSerializer,
        "unlike": SocialPostLikeSerializer,
        "bookmark": SocialPostBookmarkSerializer,
        "unbookmark": SocialPostBookmarkSerializer,
        "bookmarks": SocialPostListSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_queryset(self):
        if self.request.user.is_authenticated is False:
            qs = self.queryset.order_by('-created_at')
            return qs
        qs = self.queryset.order_by('-created_at')
        return qs

    def list(self, request):
        response = super(SocialPostViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(SocialPostViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):

        response = super(SocialPostViewset, self).create(request)

        return Response(data={"success": "Post Successfully added!!!"})

    def update(self, request, pk):
        member = SocialPost.objects.filter(id=pk).first()
        if member is None:
            return Response(data={"error": "Post not found!!!"})
        serializer = SocialPostUpdateSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):
        response = SocialPost.objects.filter(id=pk).first()
        if response is None:
            return Response(data={"error": "Post not found!!!"})
        response.delete()
        return Response(data={"success": "Post Successfuly removed!!!"})

    @action(methods=['get'], detail=False, url_path="timeline", permission_classes=[SocialPostPermission])
    def timeline(self, request):
        """
        The above function retrieves the timeline of social posts for a user by filtering posts from
        users they are following and returning the serialized data.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, user
        authentication details, and the request body
        :return: The response will contain a JSON object with a "success" key and the serialized data of
        the SocialPost objects in the "data" value.
        """
        following = Follow.objects.filter(user=request.user).values_list('followed_user', flat=True)
        posts = SocialPost.objects.filter(user__in=following.all())
        serializer = SocialPostListSerializer(posts, many=True, context={"request": request})
        return Response(data={"success": serializer.data})

    @action(methods=['get'], detail=False, url_path="bookmarks", permission_classes=[SocialPostPermission])
    def bookmarks(self, request):
        """
        This function retrieves the bookmarks of a user and returns the corresponding social posts.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the user making the request, the HTTP method used
        (GET, POST, etc.), and any data or parameters sent with the request. In this case, the `request`
        object is
        :return: The code is returning a response with a JSON object containing the serialized data of
        the SocialPost objects that are bookmarked by the current user. The serialized data is obtained
        using the SocialPostListSerializer. The JSON object has a key "success" with the value being the
        serialized data.
        """
        bookmarks = Bookmark.objects.filter(user=request.user).values_list('post', flat=True)
        posts = SocialPost.objects.filter(id__in=bookmarks.all())
        serializer = SocialPostListSerializer(posts, many=True, context={"request": request})
        return Response(data={"success": serializer.data})

    @action(methods=['post'], detail=False, url_path="like", permission_classes=[SocialPostPermission])
    def like(self, request):
        """
        This function allows a user to like a social post and returns a success message if the like is
        successful, or an error message if the user has already liked the post.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this case, it is used to retrieve the data sent in the
        request body (`
        :return: The code is returning a response in JSON format. If the post has already been liked by
        the user, it will return a response with an error message "Already Liked!!!". If the post has
        not been liked by the user, it will create a new SocialPostLike object and return a response
        with a success message "Liked!!!".
        """
        post = SocialPostLike.objects.filter(post_id=request.data["post"], user=request.user).first()
        if post is not None:
            return Response(data={"error": "Already Liked!!!"})
        SocialPostLike.objects.create(post_id=request.data["post"], user=request.user)
        return Response(data={"success": "Liked!!!"})

    @action(methods=['post'], detail=False, url_path="unlike", permission_classes=[SocialPostPermission])
    def unlike(self, request):
        """
        This function allows a user to unlike a social post by deleting their like entry from the
        database.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body. In this case, it is used to access the data sent in the
        request body
        :return: The code is returning a response in JSON format. If the member is found and deleted
        successfully, it returns a success message "DisLiked!!!". If the member is not found, it returns
        an error message "Post not found!!!".
        """
        member = SocialPostLike.objects.filter(post_id=request.data["post"], user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "DisLiked!!!"})
        else:
            return Response(data={"error": "Post not found!!!"})

    @action(methods=['post'], detail=False, url_path="bookmark", permission_classes=[SocialPostPermission])
    def bookmark(self, request):
        """
        The above function allows a user to bookmark a post if it has not already been bookmarked.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body. In this case, it is used to access the data sent in the
        request body
        :return: The code is returning a Response object with either an error message or a success
        message, depending on the outcome of the bookmarking operation. If the post has already been
        bookmarked by the user, it will return an error message stating "Already Bookmarked!!!". If the
        bookmarking operation is successful, it will return a success message stating "Bookmarked!!!".
        """
        post = Bookmark.objects.filter(post_id=request.data["post"], user=request.user).first()
        if post is not None:
            return Response(data={"error": "Already Bookmarked!!!"})
        Bookmark.objects.create(post_id=request.data["post"], user=request.user)
        return Response(data={"success": "Bookmarked!!!"})

    @action(methods=['post'], detail=False, url_path="unbookmark", permission_classes=[SocialPostPermission])
    def unbookmark(self, request):
        """
        The above function is a Django view that allows a user to unbookmark a post.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body. In this case, it is used to access the data sent in the
        request body
        :return: The code is returning a Response object with either a success message
        ("UnBookmarked!!!") or an error message ("Bookmark not found!!!").
        """
        member = Bookmark.objects.filter(post_id=request.data["post"], user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "UnBookmarked!!!"})
        else:
            return Response(data={"error": "Bookmark not found!!!"})
