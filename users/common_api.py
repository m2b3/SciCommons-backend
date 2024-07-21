"""
A common API for HashTags, Reactions, and Bookmarks
"""

from datetime import timedelta
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.utils import timezone
from ninja import Query, Router

from articles.models import Article
from articles.schemas import ArticleBasicOut, ArticleFilters
from communities.models import Community
from myapp.schemas import FilterType, Message
from posts.models import Post
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Bookmark, HashtagRelation, User
from users.schemas import (
    BookmarkSchema,
    BookmarkStatusResponseSchema,
    BookmarkToggleResponseSchema,
    BookmarkToggleSchema,
    ContentTypeEnum,
)

router = Router(tags=["Users Common API"])

"""
Bookmarks API
"""


def get_content_type(content_type_value: str) -> ContentType:
    app_label, model = content_type_value.split(".")
    return ContentType.objects.get(app_label=app_label, model=model)


@router.post(
    "/toggle-bookmark",
    response={200: BookmarkToggleResponseSchema, 400: Message},
    auth=JWTAuth(),
)
def toggle_bookmark(request, data: BookmarkToggleSchema):
    user = request.auth
    content_type = get_content_type(data.content_type.value)

    bookmark, created = Bookmark.objects.get_or_create(
        user=user, content_type=content_type, object_id=data.object_id
    )

    if created:
        return {"message": "Bookmark added successfully", "is_bookmarked": True}
    else:
        bookmark.delete()
        return {"message": "Bookmark removed successfully", "is_bookmarked": False}


@router.get(
    "/bookmark-status/{content_type}/{object_id}",
    response={200: BookmarkStatusResponseSchema, 400: Message},
    auth=OptionalJWTAuth,
)
def get_bookmark_status(request, content_type: ContentTypeEnum, object_id: int):
    user: Optional[User] = None if not request.auth else request.auth

    if not user:
        return 200, {"is_bookmarked": None}

    try:
        content_type_obj = get_content_type(content_type.value)
    except ContentType.DoesNotExist:
        return 400, {"message": "Invalid content type"}

    is_bookmarked = Bookmark.objects.filter(
        user=user, content_type=content_type_obj, object_id=object_id
    ).exists()

    return 200, {"is_bookmarked": is_bookmarked}


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


@router.get(
    "/articles/relevant-articles", response=List[ArticleBasicOut], auth=OptionalJWTAuth
)
def get_relevant_articles(request, filters: ArticleFilters = Query(...)):
    queryset = Article.objects.exclude(communityarticle__community__type="hidden")

    if filters.community_id:
        queryset = queryset.filter(
            communityarticle__community_id=filters.community_id,
            communityarticle__community__type__ne="hidden",
        )

    if filters.article_id:
        try:
            base_article = Article.objects.get(id=filters.article_id)
            base_keywords = set(
                HashtagRelation.objects.filter(
                    content_type=ContentType.objects.get_for_model(Article),
                    object_id=base_article.id,
                ).values_list("hashtag__name", flat=True)
            )

            queryset = queryset.exclude(
                id=filters.article_id
            )  # Exclude the base article
            queryset = queryset.annotate(
                relevance_score=Count(
                    "hashtagrelation",
                    filter=Q(hashtagrelation__hashtag__name__in=base_keywords),
                )
            )
            queryset = queryset.filter(relevance_score__gt=0)
            queryset = queryset.order_by("-relevance_score", "-created_at")
        except Article.DoesNotExist:
            # If the article_id is invalid, we'll just ignore it
            # and continue with other filters
            pass

    elif filters.filter_type == FilterType.POPULAR:
        queryset = queryset.annotate(
            popularity_score=Count("reviews") + Count("discussions")
        ).order_by("-popularity_score")
    elif filters.filter_type == FilterType.RECENT:
        queryset = queryset.order_by("-created_at")
    elif filters.filter_type == FilterType.RELEVANT:
        # Use the default relevance logic when no specific article_id is provided
        one_month_ago = timezone.now() - timedelta(days=30)
        queryset = queryset.filter(created_at__gte=one_month_ago).order_by(
            "-created_at"
        )

    articles = queryset[filters.offset : filters.offset + filters.limit]

    return [
        ArticleBasicOut.from_orm_with_custom_fields(article, request.auth)
        for article in articles
    ]
