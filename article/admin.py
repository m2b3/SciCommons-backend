from django.contrib import admin
from .models import Article, \
    CommentBase, \
    LikeBase, \
    Author, \
    HandlersBase, \
    ArticleModerator, \
    ArticleReviewer, \
    ArticleBlockedUser

# Register your models here.
admin.site.register(Author)
admin.site.register(Article)
admin.site.register(LikeBase)
admin.site.register(CommentBase)
admin.site.register(HandlersBase)
admin.site.register(ArticleReviewer)
admin.site.register(ArticleModerator)
admin.site.register(ArticleBlockedUser)
