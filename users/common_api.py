"""
A common API for HashTags, Reactions, and Bookmarks
"""

from datetime import timedelta
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone
from ninja import Query, Router
from ninja.errors import HttpRequest

# Todo: Move the Reaction model to the users app
from articles.models import Article, Reaction
from articles.schemas import ArticleBasicOut, ArticleFilters
from communities.models import Community
from myapp.schemas import FilterType, Message
from posts.models import Post
from posts.schemas import PaginatedPostsResponse, PostOut
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Bookmark, Hashtag, HashtagRelation, User
from users.schemas import (
    BookmarkSchema,
    BookmarkStatusResponseSchema,
    BookmarkToggleResponseSchema,
    BookmarkToggleSchema,
    ContentTypeEnum,
    HashtagOut,
    PaginatedHashtagOut,
    ReactionCountOut,
    ReactionIn,
    ReactionOut,
    SortEnum,
    VoteEnum,
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


"""
Reaction API (Like/Dislike)
"""


@router.post(
    "/reactions",
    response={200: Message, 400: Message},
    auth=JWTAuth(),
)
def post_reaction(request, reaction: ReactionIn):
    content_type = get_content_type(reaction.content_type.value)

    existing_reaction = Reaction.objects.filter(
        user=request.auth, content_type=content_type, object_id=reaction.object_id
    ).first()

    if existing_reaction:
        if existing_reaction.vote == reaction.vote.value:
            # User is clicking the same reaction type, so remove it
            existing_reaction.delete()
            return ReactionOut(
                id=None,
                user_id=request.auth.id,
                vote=None,
                created_at=None,
                message="Reaction removed",
            )
        else:
            # User is changing their reaction from like to dislike or vice versa
            existing_reaction.vote = reaction.vote.value
            existing_reaction.save()
            return ReactionOut(
                id=existing_reaction.id,
                user_id=existing_reaction.user_id,
                vote=VoteEnum(existing_reaction.vote),
                created_at=existing_reaction.created_at.isoformat(),
                message="Reaction updated",
            )
    else:
        # User is reacting for the first time
        new_reaction = Reaction.objects.create(
            user=request.auth,
            content_type=content_type,
            object_id=reaction.object_id,
            vote=reaction.vote.value,
        )
        return ReactionOut(
            id=new_reaction.id,
            user_id=new_reaction.user_id,
            vote=VoteEnum(new_reaction.vote),
            created_at=new_reaction.created_at.isoformat(),
            message="Reaction added",
        )


@router.get(
    "/reaction_count/{content_type}/{object_id}/",
    response=ReactionCountOut,
    auth=OptionalJWTAuth,
)
def get_reaction_count(request, content_type: ContentTypeEnum, object_id: int):
    content_type = get_content_type(content_type.value)

    reactions = Reaction.objects.filter(content_type=content_type, object_id=object_id)

    likes = reactions.filter(vote=VoteEnum.LIKE.value).count()
    dislikes = reactions.filter(vote=VoteEnum.DISLIKE.value).count()

    # Check if the authenticated user is the author
    current_user: Optional[User] = None if not request.auth else request.auth
    user_reaction = None

    if current_user:
        user_reaction_obj = reactions.filter(user=current_user).first()
        if user_reaction_obj:
            user_reaction = VoteEnum(user_reaction_obj.vote)

    return ReactionCountOut(
        likes=likes,
        dislikes=dislikes,
        user_reaction=user_reaction,
    )


"""
Hashtags API
"""


@router.get("/hashtags/", response=PaginatedHashtagOut)
def get_hashtags(
    request,
    sort: SortEnum = Query(SortEnum.POPULAR),
    search: str = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
):
    """
    Get a list of hashtags from the database.
    """
    hashtags = Hashtag.objects.annotate(count=Count("hashtagrelation"))

    if search:
        hashtags = hashtags.filter(name__icontains=search)

    if sort == SortEnum.POPULAR:
        hashtags = hashtags.order_by("-count", "name")
    elif sort == SortEnum.RECENT:
        hashtags = hashtags.order_by("-id")
    else:  # ALPHABETICAL
        hashtags = hashtags.order_by("name")

    paginator = Paginator(hashtags, per_page)
    page_obj = paginator.get_page(page)

    return PaginatedHashtagOut(
        items=[HashtagOut(name=h.name, count=h.count) for h in page_obj.object_list],
        total=paginator.count,
        page=page_obj.number,
        per_page=per_page,
        pages=paginator.num_pages,
    )


# Todo: Delete this API endpoint
@router.get("/my-posts", response=PaginatedPostsResponse, auth=JWTAuth())
def list_my_posts(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at", enum=["created_at", "title"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    hashtag: Optional[str] = Query(None),
):
    user = request.auth
    posts = Post.objects.filter(author=user, is_deleted=False)

    # Apply hashtag filtering
    if hashtag:
        hashtag_id = (
            Hashtag.objects.filter(name=hashtag).values_list("id", flat=True).first()
        )
        if hashtag_id:
            post_ids = HashtagRelation.objects.filter(
                hashtag_id=hashtag_id,
                content_type=ContentType.objects.get_for_model(Post),
            ).values_list("object_id", flat=True)
            posts = posts.filter(id__in=post_ids)

    # Todo: Add Filter for sorting by post reactions
    # Apply sorting
    order_prefix = "-" if sort_order == "desc" else ""
    posts = posts.order_by(f"{order_prefix}{sort_by}")

    paginator = Paginator(posts, size)
    page_obj = paginator.get_page(page)
    return PaginatedPostsResponse(
        items=[PostOut.resolve_post(post, user) for post in page_obj],
        total=paginator.count,
        page=page,
        size=size,
    )
