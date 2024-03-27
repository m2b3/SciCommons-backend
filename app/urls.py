from rest_framework import routers
from django.urls import include, path
from django.conf.urls.static import static

from app.views import *
from community.views import CommunityViewset
from user.views import UserViewset, NotificationViewset
from article.views import CommentViewset, ArticleViewset
from chat.views import PersonalMessageViewset, ArticleChatViewset
from social.views import SocialPostViewset, SocialPostCommentViewset

router = routers.DefaultRouter()
router.register(r'user', UserViewset)
router.register(r'community', CommunityViewset)
router.register(r'article', ArticleViewset)
router.register(r'comment', CommentViewset)
router.register(r'chat', PersonalMessageViewset)
router.register(r'notification', NotificationViewset)
router.register(r'feed', SocialPostViewset)
router.register(r'feedcomment', SocialPostCommentViewset)
router.register(r"article_chat", ArticleChatViewset)

urlpatterns = [path("", include(router.urls)), ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
