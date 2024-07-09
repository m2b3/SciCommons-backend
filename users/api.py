from enum import Enum
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count
from ninja import Query, Router
from ninja.errors import HttpRequest
from ninja.responses import codes_4xx, codes_5xx

# Todo: Move the Reaction model to the users app
from articles.models import Article, Reaction
from articles.schemas import ArticleOut, PaginatedArticlesResponse
from posts.models import Post
from posts.schemas import PaginatedPostsResponse, PostOut
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Hashtag, HashtagRelation, Notification, User
from users.schemas import (
    ContentTypeEnum,
    HashtagOut,
    Message,
    NotificationSchema,
    PaginatedHashtagOut,
    ReactionCountOut,
    ReactionIn,
    ReactionOut,
    SortEnum,
    VoteEnum,
)

router = Router(tags=["Users"])


class StatusFilter(str, Enum):
    UNSUBMITTED = "unsubmitted"
    PUBLISHED = "published"


@router.get(
    "/my-articles",
    response={200: PaginatedArticlesResponse, 400: Message, 500: Message},
    auth=JWTAuth(),
)
def get_my_articles(
    request,
    status_filter: Optional[StatusFilter] = Query(None),
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0, le=100),
):
    articles = Article.objects.filter(submitter=request.auth).order_by("-created_at")

    if status_filter == StatusFilter.PUBLISHED:
        articles = articles.filter(published=True)
    elif status_filter == StatusFilter.UNSUBMITTED:
        articles = articles.filter(status="Pending", community=None)

    paginator = Paginator(articles, limit)
    paginated_articles = paginator.get_page(page)

    return 200, PaginatedArticlesResponse(
        items=[
            ArticleOut.from_orm_with_custom_fields(article, request.auth)
            for article in paginated_articles
        ],
        total=paginator.count,
        page=page,
        page_size=limit,
        num_pages=paginator.num_pages,
    )


def get_content_type(content_type_value: str) -> ContentType:
    app_label, model = content_type_value.split(".")
    return ContentType.objects.get(app_label=app_label, model=model)


@router.post(
    "/reactions",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
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


@router.get(
    "/notifications",
    response={200: List[NotificationSchema], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_notifications(request):
    try:
        user_notifications = Notification.objects.filter(user=request.auth).order_by(
            "-created_at"
        )

        return 200, [
            NotificationSchema(
                **{
                    "id": notif.id,
                    "message": notif.message,
                    "content": notif.content,
                    "isRead": notif.is_read,
                    "link": notif.link,
                    "category": notif.category,
                    "notificationType": notif.notification_type,
                    "createdAt": notif.created_at,
                    "expiresAt": notif.expires_at,
                }
            )
            for notif in user_notifications
        ]
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/notifications/{notification_id}/mark-as-read",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def mark_notification_as_read(request, notification_id: int):
    try:
        notification = Notification.objects.get(pk=notification_id, user=request.auth)
        if not notification:
            return 404, {"message": "Notification does not exist."}

        if not notification.is_read:
            notification.is_read = True
            notification.save()
            return {"message": "Notification marked as read."}
        else:
            return {"message": "Notification was already marked as read."}
    except Exception as e:
        return 500, {"message": str(e)}


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


@router.get("/my-posts", response=PaginatedPostsResponse, auth=JWTAuth())
def list_my_posts(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at", enum=["created_at", "title"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    hashtags: Optional[List[str]] = Query(None),
):
    user = request.auth
    posts = Post.objects.filter(author=user, is_deleted=False)

    # Apply hashtag filtering
    if hashtags:
        hashtag_ids = Hashtag.objects.filter(name__in=hashtags).values_list(
            "id", flat=True
        )
        post_ids = HashtagRelation.objects.filter(
            hashtag_id__in=hashtag_ids,
            content_type=ContentType.objects.get_for_model(Post),
        ).values_list("object_id", flat=True)
        posts = posts.filter(id__in=post_ids).distinct()

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
