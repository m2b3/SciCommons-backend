from django.contrib import admin
from .models import *

# Register your models here.
# The code `admin.site.register(ModelName)` is used to register the models in the Django admin
# interface.
admin.site.register(User)
admin.site.register(ForgetPassword)
admin.site.register(Community)
admin.site.register(OfficialReviewer)
admin.site.register(Article)
admin.site.register(CommentBase)
admin.site.register(PersonalMessage)
admin.site.register(LikeBase)
admin.site.register(Rank)
admin.site.register(Notification)
admin.site.register(Subscribe)
admin.site.register(Author)
admin.site.register(Favourite)
admin.site.register(Follow)
admin.site.register(SocialPost)
admin.site.register(SocialPostComment)
admin.site.register(BookMark)
admin.site.register(ArticleMessage)