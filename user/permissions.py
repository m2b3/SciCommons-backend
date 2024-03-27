from rest_framework import permissions


# The UserPermission class defines the permissions for different actions in a Django REST framework
# view, allowing certain actions for authenticated users and others for all users.
class UserPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['list', 'retrieve', 'getUserArticles', 'getposts', 'followers', 'following']:
            return True

        if view.action in [
            'create', 'login', 'refresh_token',
            'forgot_password', 'reset_password',
        ]:
            return True
        elif view.action in [
            'update', 'partial_update', 'destroy',
            'change_password', 'getMyArticle', 'getMyArticles', 'getMyCommunity', 'messages', 'getmyposts'
        ]:
            return request.user.is_authenticated and request.user == obj
        else:
            return False


# The GeneralPermission class checks if a user has permission to perform certain actions in a view
# based on their authentication status.
class GeneralPermission(permissions.BasePermission):

    def has_permission(self, request, view):

        if view.action in ['list', 'retrieve']:
            return True

        elif view.action in ['create', 'update', 'destroy']:
            return request.user.is_authenticated


# The `NotificationPermission` class is a custom permission class in Django that checks if a user has
# permission to perform certain actions on a notification object.
class NotificationPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list']:
            return request.user.is_authenticated

        if view.action in ['destroy']:
            return obj.user == request.user


# The `FavouritePermission` class defines the permissions for different actions in a view, allowing
# certain actions based on user authentication and ownership of the object.
class FavouritePermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list']:
            return True

        elif view.action in ['create', 'like']:
            return request.user.is_authenticated

        elif view.action == 'destroy':
            return obj.user == request.user
