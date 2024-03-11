from rest_framework import routers

from article.views import ArticleViewset, CommentViewset

router = routers.DefaultRouter()
router.register(r'article', ArticleViewset)
router.register(r'comment', CommentViewset)

urlpatterns = router.urls
