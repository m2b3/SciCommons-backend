from rest_framework import permissions


# The `MessagePermissions` class defines the permissions for different actions on a message object
# based on the sender and receiver.
class MessagePermissions(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if view.action in ["list", "retrive"]:
            if obj.sender == request.User or obj.receiver == request.user:
                return True
            else:
                return False

        elif view.action in ["destroy", "update"]:
            return obj.sender == request.user


# The `ArticleChatPermissions` class defines the permissions for different actions on an article chat
# object, including listing, retrieving, destroying, and updating.

class ArticleChatPermissions(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):

        if request.user in obj.article.blocked_users.all():
            return False

        if view.action in ["list", "retrive"]:
            if obj.sender == request.User or obj.receiver == request.user:
                return True
            else:
                return False

        elif view.action in ["destroy"]:
            if obj.sender == request.user:
                return True
            elif request.user in obj.article.moderator.all():
                return True
            else:
                return False

        elif view.action in ["update"]:
            if obj.sender == request.user:
                return True
            else:
                return False
