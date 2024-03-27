from django.contrib import admin
from .models import User, ForgetPassword, Rank, Notification, Subscribe, Favourite

# Register your models here.
admin.site.register(User)
admin.site.register(ForgetPassword)
admin.site.register(Rank)
admin.site.register(Notification)
admin.site.register(Subscribe)
admin.site.register(Favourite)
