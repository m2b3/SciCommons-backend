# The `SocialPostPermission` class defines the permissions for different actions on social posts, such
# as retrieving, creating, updating, and deleting.
from rest_framework import permissions


class SocialPostPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'getMyPosts']:
            return True

        elif view.action in ['create', 'like', 'unlike', 'bookmarks']:
            return request.user.is_authenticated

        elif view.action in ['destroy', 'update', 'bookmark', 'unbookmark']:
            return obj.user == request.user


# The `SocialPostCommentPermission` class defines the permissions for different actions on social post
# comments, allowing retrieval and listing for all users, creation and liking/unliking for
# authenticated users, and deletion and updating only by the comment owner.
class SocialPostCommentPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list']:
            return True

        elif view.action in ['create', 'like', 'unlike']:
            return request.user.is_authenticated

        elif view.action in ['destroy', 'update']:
            return obj.user == request.user


# The `FollowPermission` class defines the permissions for different actions in a view, allowing users
# to retrieve and list objects, create and like objects if authenticated, and destroy objects if they
# belong to the requesting user.
class FollowPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list']:
            return True

        elif view.action in ['create', 'like']:
            return request.user.is_authenticated

        elif view.action in ['destroy']:
            return obj.user == request.user
