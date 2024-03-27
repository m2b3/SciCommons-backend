from rest_framework import permissions

from community.models import CommunityMember


# The `CommunityPermission` class defines the permissions for different actions in a community,
# allowing certain actions for admins and authenticated users.
class CommunityPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'getArticles']:
            return True

        elif view.action in ['update', 'getMembers', 'addPublishedInfo', 'destroy'
            , 'remove_member', 'promote_member', 'get_requests', 'approve_request']:
            admins = CommunityMember.objects.filter(community=obj, is_admin=True)
            if request.user in [admin.user for admin in admins]:
                return True
            else:
                return False

        elif view.action in ['create', 'subscribe', 'unsubscribe', 'join_request']:
            return request.user.is_authenticated

        return obj.user == request.user
