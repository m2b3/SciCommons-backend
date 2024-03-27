from django.db.models import Q
from rest_framework import viewsets, parsers, status
from rest_framework.response import Response

from chat.models import PersonalMessage, ArticleMessage
from chat.permissions import MessagePermissions, ArticleChatPermissions
from chat.serializer import MessageSerializer, MessageCreateSerializer, MessageUpdateSerializer
from chat.serializer.article import ArticleChatSerializer, ArticleChatCreateSerializer, ArticleChatUpdateSerializer


# Create your views here.
class ArticleChatViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling CRUD operations on ArticleMessage objects.
    # It specifies the queryset to retrieve all ArticleMessage objects, sets the permission classes to
    # ArticleChatPermissions, and sets the parser classes to JSONParser, MultiPartParser, and
    # FormParser. The serializer_class is set to ArticleChatSerializer, which will be used to
    # serialize and deserialize ArticleMessage objects. The http_method_names are set to allow POST,
    # GET, PUT, and DELETE requests. The action_serializer dictionary maps different actions (create,
    # retrieve, list, update, destroy) to different serializers for handling those actions.
    queryset = ArticleMessage.objects.all()
    permission_classes = [ArticleChatPermissions]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = ArticleChatSerializer
    http_method_names = ["post", "get", "put", "delete"]

    action_serializer = {
        "create": ArticleChatCreateSerializer,
        "retrieve": ArticleChatSerializer,
        "list": ArticleChatSerializer,
        "update": ArticleChatUpdateSerializer,
        "destroy": ArticleChatSerializer
    }

    def get_serializer_class(self):
        return self.action_serializer.get(self.action, self.serializer_class)

    def get_queryset(self):
        article = self.request.query_params.get("article", None)
        if article is not None:
            qs = self.queryset.filter(article_id=article).order_by("created_at")
            return qs
        return ArticleMessage.objects.none()

    def list(self, request):
        response = super(ArticleChatViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(ArticleChatViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):
        response = super(ArticleChatViewset, self).create(request)

        return Response(data={"success": response.data})

    def update(self, request, pk):
        self.get_object()
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):
        super(ArticleChatViewset, self).destroy(request, pk=pk)

        return Response(data={"success": "chat successfully deleted"})


class PersonalMessageViewset(viewsets.ModelViewSet):
    queryset = PersonalMessage.objects.all()
    permission_classes = [MessagePermissions]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = MessageSerializer
    http_method_names = ["get", "post", "delete", "put"]

    action_serializers = {
        "create": MessageCreateSerializer,
        "retrieve": MessageSerializer,
        "list": MessageSerializer,
        "update": MessageUpdateSerializer,
        "destroy": MessageSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_queryset(self):
        qs = self.queryset.filter(Q(sender=self.request.user) | Q(receiver=self.request.user)).order_by('-created_at')
        return qs

    def list(self, request):
        response = super(PersonalMessageViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(PersonalMessageViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            data={"success": "Message Successfully sent", "message": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        super(PersonalMessageViewset, self).destroy(request, pk)

        return Response(data={"success": "Message Successfuly removed!!!"})