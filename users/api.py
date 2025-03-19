from enum import Enum
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from ninja import File, Query, Router, UploadedFile
from ninja.errors import HttpRequest
from ninja.responses import codes_4xx, codes_5xx

# Todo: Move the Reaction model to the users app
from articles.models import Article, Reaction
from communities.models import Community
from myapp.schemas import Message, UserStats
from posts.models import Post
from users.auth import JWTAuth
from users.models import Bookmark, Hashtag, HashtagRelation, Notification, User
from users.schemas import (
    BookmarkSchema,
    FavoriteItemSchema,
    NotificationSchema,
    UserArticleSchema,
    UserCommunitySchema,
    UserDetails,
    UserPostSchema,
    UserUpdateSchema,
)

router = Router(tags=["Users"])


class StatusFilter(str, Enum):
    UNSUBMITTED = "unsubmitted"
    PUBLISHED = "published"


"""
User's Profile API
"""


# Get user details
@router.get("/me", response={200: UserDetails, 401: Message}, auth=JWTAuth())
def get_me(request: HttpRequest):
    return UserDetails.resolve_user(request.auth)


# Update user details
@router.put("/me", response={200: UserDetails, 401: Message}, auth=JWTAuth())
def update_user(
    request: HttpRequest,
    payload: UserUpdateSchema,
    profile_image: File[UploadedFile] = None,
):
    user: User = request.auth

    user.first_name = payload.details.first_name
    user.last_name = payload.details.last_name
    user.bio = payload.details.bio
    user.google_scholar_url = payload.details.google_scholar_url
    user.home_page_url = payload.details.home_page_url
    user.linkedin_url = payload.details.linkedin_url
    user.github_url = payload.details.github_url
    user.academic_statuses = [
        academic_status.dict() for academic_status in payload.details.academic_statuses
    ]

    if payload.details.research_interests:
        # Use hashtags to store research interests
        content_type = ContentType.objects.get_for_model(User)
        HashtagRelation.objects.filter(
            content_type=content_type, object_id=user.id
        ).delete()
        for hashtag_name in payload.details.research_interests:
            hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
            HashtagRelation.objects.create(
                hashtag=hashtag, content_type=content_type, object_id=user.id
            )

    user.save()
    return UserDetails.resolve_user(user)


# Get UserStats
@router.get("/me/stats", response={200: UserStats, 401: Message}, auth=JWTAuth())
def get_user_stats(request: HttpRequest):
    return UserStats.from_model(request.auth)


"""
User's Content API
"""


@router.get(
    "/contributed-articles",
    response={200: List[UserArticleSchema], 400: Message, 500: Message},
    auth=JWTAuth(),
)
def get_my_articles(request: HttpRequest):
    user = request.auth
    articles = Article.objects.filter(submitter=user).order_by("-created_at")
    return articles


@router.get(
    "/my-communities",
    response={200: List[UserCommunitySchema], 400: Message, 500: Message},
    auth=JWTAuth(),
)
def get_my_communities(request):
    user = request.auth
    communities = []

    # Get communities where the user is an admin
    admin_communities = user.admin_communities.annotate(members_count=Count("members"))
    for community in admin_communities:
        communities.append(
            {
                "name": community.name,
                "role": "Admin",
                "members_count": community.members_count,
            }
        )

    # Get communities where the user is a reviewer
    reviewer_communities = user.reviewer_communities.annotate(
        members_count=Count("members")
    )
    for community in reviewer_communities:
        if community.name not in [c["name"] for c in communities]:
            communities.append(
                {
                    "name": community.name,
                    "role": "Reviewer",
                    "members_count": community.members_count,
                }
            )

    # Get communities where the user is a moderator
    moderator_communities = user.moderator_communities.annotate(
        members_count=Count("members")
    )
    for community in moderator_communities:
        if community.name not in [c["name"] for c in communities]:
            communities.append(
                {
                    "name": community.name,
                    "role": "Moderator",
                    "members_count": community.members_count,
                }
            )

    # Get communities where the user is a member
    member_communities = user.member_communities.annotate(
        members_count=Count("members")
    )
    for community in member_communities:
        if community.name not in [c["name"] for c in communities]:
            communities.append(
                {
                    "name": community.name,
                    "role": "Member",
                    "members_count": community.members_count,
                }
            )

    return communities


@router.get(
    "/contributed-posts",
    response={200: List[UserPostSchema], 400: Message, 500: Message},
    auth=JWTAuth(),
)
def get_my_posts(request):
    user = request.auth
    posts = Post.objects.filter(author=user, is_deleted=False).order_by("-created_at")
    post_content_type = ContentType.objects.get_for_model(Post)

    result = []
    for post in posts:
        likes_count = Reaction.objects.filter(
            content_type=post_content_type, object_id=post.id, vote=Reaction.LIKE
        ).count()

        # Determine the most recent action (creation or comment)
        latest_comment = (
            post.post_comments.filter(is_deleted=False).order_by("-created_at").first()
        )
        if latest_comment and latest_comment.created_at > post.created_at:
            action = "Commented"
            action_date = latest_comment.created_at
        else:
            action = "Created"
            action_date = post.created_at

        result.append(
            {
                "id": post.id,
                "title": post.title,
                "created_at": post.created_at,
                "likes_count": likes_count,
                "action": action,
                "action_date": action_date,
            }
        )

    return result


@router.get(
    "/my-favorites",
    response={200: List[FavoriteItemSchema], 400: Message, 500: Message},
    auth=JWTAuth(),
)
def get_my_favorites(request):
    user = request.auth
    favorites = []

    # Get content types
    article_type = ContentType.objects.get_for_model(Article)
    community_type = ContentType.objects.get_for_model(Community)
    post_type = ContentType.objects.get_for_model(Post)

    # Get user's liked items
    liked_items = Reaction.objects.filter(user=user, vote=Reaction.LIKE)

    for item in liked_items:
        if item.content_type == article_type:
            article: Article = item.content_object
            favorites.append(
                {
                    "title": article.title,
                    "type": "Article",
                    "details": f"Article by {article.submitter.username}",
                    "tag": "Article",
                    "slug": article.slug,
                }
            )
        elif item.content_type == community_type:
            community: Community = item.content_object
            favorites.append(
                {
                    "title": community.name,
                    "type": "Community",
                    "details": f"{community.members.count()} members",
                    "tag": "Community",
                    "slug": community.slug,
                }
            )
        elif item.content_type == post_type:
            post = item.content_object
            favorites.append(
                {
                    "title": post.title,
                    "type": "Post",
                    "details": (
                        f"Post by {post.author.username} · "
                        f"{post.reactions.filter(vote=Reaction.LIKE).count()} likes"
                    ),
                    "tag": "Post",
                    "slug": str(post.id),
                }
            )

    return favorites


@router.get(
    "/bookmarks", response={200: List[BookmarkSchema], 400: Message}, auth=JWTAuth()
)
def get_my_bookmarks(request):
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
                    "slug": obj.slug,
                }
            )
        elif isinstance(obj, Community):
            result.append(
                {
                    "id": bookmark.id,
                    "title": obj.name,
                    "type": "Community",
                    "details": f"{obj.members.count()} members",
                    "slug": obj.slug,
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
                    "slug": str(obj.id),
                }
            )

    return result


"""
Notification API
"""


@router.get(
    "/notifications",
    response={200: List[NotificationSchema], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_notifications(
    request,
    article_slug: Optional[str] = Query(None, description="Filter by article slug"),
    community_id: Optional[int] = Query(None, description="Filter by community ID"),
    post_id: Optional[int] = Query(None, description="Filter by post ID"),
):
    user_notifications = Notification.objects.filter(user=request.auth)

    # Apply filters based on query parameters
    filters = Q()
    if article_slug:
        filters |= Q(article__slug=article_slug)
    if community_id:
        filters |= Q(community_id=community_id)
    if post_id:
        filters |= Q(post_id=post_id)

    if filters:
        user_notifications = user_notifications.filter(filters)

    user_notifications = user_notifications.order_by("-created_at")

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
