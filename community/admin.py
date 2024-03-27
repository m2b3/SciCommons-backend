from django.contrib import admin
from .models import (
    OfficialReviewer, CommunityMeta, CommunityMember, CommunityRequests, UnregisteredUser, Community, Moderator
)

# Register your models here.
admin.site.register(Community)
admin.site.register(OfficialReviewer)
admin.site.register(CommunityMeta)
admin.site.register(CommunityMember)
admin.site.register(CommunityRequests)
admin.site.register(UnregisteredUser)
admin.site.register(Moderator)
