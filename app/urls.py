from django.conf.urls.static import static
from django.urls import include, path
from rest_framework import routers

from app.views import *

router = routers.DefaultRouter()
router.register(r'user', UserViewset)
router.register(r'community', CommunityViewset)
router.register(r'chat', PersonalMessageViewset)
router.register(r'notification', NotificationViewset)
router.register(r'feed', SocialPostViewset)
router.register(r'feedcomment', SocialPostCommentViewset)
router.register(r"article_chat", ArticleChatViewset)

urlpatterns = [
    path("", include(router.urls)),
    path("", include("article.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
