from django.contrib import admin
from .models import ArticleMessage, BlockPersonalMessage, PersonalMessage

# Register your models here.
admin.site.register(ArticleMessage)
admin.site.register(PersonalMessage)
admin.site.register(BlockPersonalMessage)