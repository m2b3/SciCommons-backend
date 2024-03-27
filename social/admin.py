from django.contrib import admin

from social.models import SocialPostComment, SocialPost, Bookmark, Follow

# Register your models here.
admin.site.register(Follow)
admin.site.register(SocialPost)
admin.site.register(SocialPostComment)
admin.site.register(Bookmark)
