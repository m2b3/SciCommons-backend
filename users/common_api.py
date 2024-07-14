"""
A common API for HashTags, Reactions, and Bookmarks
"""

from typing import List

from django.contrib.contenttypes.models import ContentType
from ninja import Router

from articles.models import Article
from communities.models import Community
from posts.models import Post
from users.auth import JWTAuth
from users.models import Bookmark
from users.schemas import (
    BookmarkSchema,
    BookmarkToggleResponseSchema,
    BookmarkToggleSchema,
)

router = Router(tags=["Users Common API"])

"""
Bookmarks API
"""


@router.post("/toggle-bookmark", response=BookmarkToggleResponseSchema, auth=JWTAuth())
def toggle_bookmark(request, data: BookmarkToggleSchema):
    user = request.auth
    content_type = ContentType.objects.get(model=data.content_type.lower())

    bookmark, created = Bookmark.objects.get_or_create(
        user=user, content_type=content_type, object_id=data.object_id
    )

    if created:
        return {"message": "Bookmark added successfully", "is_bookmarked": True}
    else:
        bookmark.delete()
        return {"message": "Bookmark removed successfully", "is_bookmarked": False}


@router.get("/bookmarks", response=List[BookmarkSchema], auth=JWTAuth())
def get_bookmarks(request):
    user = request.auth
    bookmarks = Bookmark.objects.filter(user=user).select_related("content_type")

    result = []
    for bookmark in bookmarks:
        obj = bookmark.content_object
        if isinstance(obj, Article):
            result.append(
                {
                    "id": bookmark.id,
                    "title": obj.title,
                    "type": "Article",
                    "details": f"Article by {obj.author.get_full_name()}",
                }
            )
        elif isinstance(obj, Community):
            result.append(
                {
                    "id": bookmark.id,
                    "title": obj.name,
                    "type": "Community",
                    "details": f"{obj.members.count()} members",
                }
            )
        elif isinstance(obj, Post):
            result.append(
                {
                    "id": bookmark.id,
                    "title": obj.title,
                    "type": "Post",
                    "details": (
                        f"Post by {obj.author.username} · "
                        f"{obj.reactions.filter(vote=1).count()} likes"
                    ),
                }
            )

    return result
