from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_swagger.views import get_swagger_view
from rest_framework import permissions
from drf_yasg import views, openapi
from django.http import HttpResponse
from django.conf import settings
from rest_framework import routers
from django.urls import include, path
from django.conf.urls.static import static

from community.views import CommunityViewset
from user.views import UserViewset, NotificationViewset
from article.views import CommentViewset, ArticleViewset
from chat.views import PersonalMessageViewset, ArticleChatViewset
from social.views import SocialPostViewset, SocialPostCommentViewset

schema_view = get_swagger_view(title="APIs")

redoc_schema_view = views.get_schema_view(
    openapi.Info(
        title="APIs",
        default_version='v1',
        description="API Documentation",
        terms_of_service="#",
    ),
    public=True,
)


def myindex(request):
    return HttpResponse("backend server is running")


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

urlpatterns = [
    path('docs/', redoc_schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', redoc_schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('', myindex, name='index')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
