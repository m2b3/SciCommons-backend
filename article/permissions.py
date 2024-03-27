from rest_framework import permissions

from article.models import ArticleModerator, Author
from community.models import CommunityMember


# The `ArticlePermission` class defines the permissions for various actions on an article object based
# on the user's role and the action being performed.
class ArticlePermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'updateViews']:
            return True

        elif view.action in ['create', 'submit_article', 'favourite', 'unfavourite', 'favourites']:
            return request.user.is_authenticated

        elif view.action in ['approve_article']:
            member = ArticleModerator.objects.filter(article=obj.id, moderator__user=request.user,
                                                     moderator__community=request.data['community']).first()
            if member is None:
                return False
            else:
                return True

        elif view.action in ['approve_review', 'reject_article']:
            admin = CommunityMember.objects.filter(user=request.user, community=request.data['community']).first()
            return admin.is_admin

        elif view.action in ['destroy', 'update', 'getPublished', 'getIsapproved', 'status']:
            if Author.objects.filter(User=request.user, article=obj).first():
                return True
            else:
                return False


# The CommentPermission class defines the permissions for different actions on a comment object, such
# as retrieving, creating, updating, and deleting.
class CommentPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):

        if view.action in ['retrieve', 'list', 'parents']:
            return True

        elif view.action in ['create', 'like']:
            return request.user.is_authenticated

        elif view.action in ['update']:
            return obj.User == request.user

        elif view.action in ['block_user', 'destroy']:
            member = ArticleModerator.objects.filter(article=obj.id, moderator__user=request.user).first()
            if member is None:
                return False
            return True
