from rest_framework import viewsets, parsers
from rest_framework.response import Response

from user.models import Notification
from user.permissions import NotificationPermission
from user.serializer.subscription import NotificationSerializer


class NotificationViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling notifications. It is using the
    # `Notification` model to retrieve all notification objects from the database. The view has a
    # permission class called `NotificationPermission` which controls access to the view. It also
    # specifies the parser classes for handling different types of data formats (JSON, multipart, form
    # data). The view uses the `NotificationSerializer` to serialize the notification objects and
    # return them as a response. The allowed HTTP methods for this view are GET, PUT, and DELETE.
    queryset = Notification.objects.all()
    permission_classes = [NotificationPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = NotificationSerializer
    http_method_names = ['get', 'put', 'delete']

    def get_queryset(self):
        qs = self.queryset.filter(user=self.request.user).order_by('-date')
        return qs

    def list(self, request):
        response = super(NotificationViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(NotificationViewset, self).retrieve(request, pk=pk)

        return Response(data={"success": response.data})

    def update(self, request, pk):
        instance = Notification.objects.filter(id=pk).first()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": "notification marked!!!"})

    def destroy(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(NotificationViewset, self).destroy(request, pk)

        return Response(data={"success": "Notification deleted successfully."})
