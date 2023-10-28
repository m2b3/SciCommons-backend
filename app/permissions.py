from rest_framework import permissions

from app.models import *
from app.serializer import *

# The UserPermission class defines the permissions for different actions in a Django REST framework
# view, allowing certain actions for authenticated users and others for all users.
class UserPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        
        if view.action in ['list', 'retrieve', 'getUserArticles', 'getposts','followers', 'following']:
            return True
        
        if view.action in [
            'create', 'login', 'refresh_token',
            'forgot_password', 'reset_password',
            ]:
            return True
        elif view.action in [
             'update', 'partial_update', 'destroy',
            'change_password','getMyArticle', 'getMyArticles','getMyCommunity', 'messages','getmyposts'
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
        
# The `CommunityPermission` class defines the permissions for different actions in a community,
# allowing certain actions for admins and authenticated users.
class CommunityPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'getArticles']:
            return True
        
        elif view.action in ['update', 'getMembers', 'addPublishedInfo', 'destroy'
                             , 'remove_member', 'promote_member', 'get_requests', 'approve_request']:
            admins = CommunityMember.objects.filter(community=obj,is_admin=True)
            if request.user in [ admin.user for admin in admins]:
                return True
            else:
                return False
        
        elif view.action in ['create', 'subscribe','unsubscribe', 'join_request']:
            return request.user.is_authenticated
        
        return obj.user == request.user
       
# The `ArticlePermission` class defines the permissions for various actions on an article object based
# on the user's role and the action being performed.
class ArticlePermission(permissions.BasePermission):
    
    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'updateViews']:
            return True
        
        elif view.action in ['create', 'submit_article','favourite','unfavourite', 'favourites']:
            return request.user.is_authenticated
        
        elif view.action in ['approve_article']:
            member = ArticleModerator.objects.filter(article=obj.id,moderator__user=request.user,moderator__community=request.data['community']).first()
            if member is None:
                return False
            else:
                return True
        
        elif view.action in ['approve_review','reject_article']:
            admin = CommunityMember.objects.filter(user=request.user, community=request.data['community']).first()
            return admin.is_admin

        elif view.action in [ 'destroy', 'update','getPublished', 'getIsapproved','status']:
            if Author.objects.filter(User=request.user, article=obj).first():
                return True
            else:
                return False


# The CommentPermission class defines the permissions for different actions on a comment object, such
# as retrieving, creating, updating, and deleting.
class CommentPermission(permissions.BasePermission):
    
    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list']:
            return True
        
        elif view.action in ['create', 'like']:
            return request.user.is_authenticated
        
        elif view.action in ['update']:
            return obj.User == request.user
        
        elif view.action in ['block_user', 'destroy']:
            member = ArticleModerator.objects.filter(article=obj.id,moderator__user=request.user).first()
            if member is None:
                return False
            return True


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
        
# The `SocialPostPermission` class defines the permissions for different actions on social posts, such
# as retrieving, creating, updating, and deleting.
class SocialPostPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list','getMyPosts']:
            return True
        
        elif view.action in ['create', 'like','unlike', 'bookmarks']:
            return request.user.is_authenticated
        
        elif view.action in ['destroy', 'update','bookmark','unbookmark']:
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
        
        elif view.action in [ 'destroy', 'update']:
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