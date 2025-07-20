from enum import Enum
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from ninja import File, Query, Router, UploadedFile
from ninja.errors import HttpRequest
from ninja.responses import codes_4xx, codes_5xx

# Todo: Move the Reaction model to the users app
from articles.models import Article, Reaction, Review
from articles.schemas import (
    ArticlesListOut,
    Message,
    PaginatedArticlesListResponse,
)
from communities.models import Community, CommunityArticle, Membership
from communities.schemas import CommunityListOut, PaginatedCommunities
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
@router.get(
    "/me",
    response={200: UserDetails, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_me(request: HttpRequest):
    try:
        return 200, UserDetails.resolve_user(request.auth)
    except Exception:
        return 500, {"message": "Error retrieving user details. Please try again."}


# Update user details
@router.put(
    "/me",
    response={200: UserDetails, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_user(
    request: HttpRequest,
    payload: UserUpdateSchema,
    profile_image: File[UploadedFile] = None,
):
    try:
        user: User = request.auth

        try:
            user.first_name = payload.details.first_name
            user.last_name = payload.details.last_name
            user.bio = payload.details.bio
            user.google_scholar_url = payload.details.google_scholar_url
            user.home_page_url = payload.details.home_page_url
            user.linkedin_url = payload.details.linkedin_url
            user.github_url = payload.details.github_url
            user.academic_statuses = [
                academic_status.dict()
                for academic_status in payload.details.academic_statuses
            ]
        except Exception:
            return 500, {
                "message": "Error updating profile information. Please try again."
            }

        if payload.details.research_interests:
            try:
                # Use hashtags to store research interests
                content_type = ContentType.objects.get_for_model(User)
                HashtagRelation.objects.filter(
                    content_type=content_type, object_id=user.id
                ).delete()

                for hashtag_name in payload.details.research_interests:
                    hashtag, created = Hashtag.objects.get_or_create(
                        name=hashtag_name.lower()
                    )
                    HashtagRelation.objects.create(
                        hashtag=hashtag, content_type=content_type, object_id=user.id
                    )
            except Exception:
                return 500, {
                    "message": "Error updating research interests. Please try again."
                }

        try:
            user.save()
        except Exception:
            return 500, {"message": "Error saving user profile. Please try again."}

        return 200, UserDetails.resolve_user(user)
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get UserStats
@router.get(
    "/me/stats",
    response={200: UserStats, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_user_stats(request: HttpRequest):
    try:
        return 200, UserStats.from_model(request.auth)
    except Exception:
        return 500, {"message": "Error retrieving user statistics. Please try again."}


"""
User's Content API
"""


@router.get(
    "/contributed-articles",
    response={200: List[UserArticleSchema], codes_4xx: Message, codes_5xx: Message},
    summary="Get Contributed Articles",
    auth=JWTAuth(),
)
def get_my_articles(request: HttpRequest):
    try:
        user = request.auth
        try:
            articles = Article.objects.filter(submitter=user).order_by("-created_at")
            return 200, articles
        except Exception:
            return 500, {"message": "Error retrieving your articles. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get My Articles
@router.get(
    "/my-articles",
    response={
        200: PaginatedArticlesListResponse,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    summary="Get My Articles",
    auth=JWTAuth(),
)
def list_my_articles(
    request, page: int = 1, per_page: int = 10, search: Optional[str] = None
):
    try:
        articles = Article.objects.filter(submitter=request.auth).order_by(
            "-created_at"
        )
    except Exception:
        return 500, {"message": "Error retrieving articles. Please try again."}

    try:
        if search:
            articles = articles.filter(title__icontains=search)

        paginator = Paginator(articles, per_page)
        paginated_articles = paginator.get_page(page)
    except Exception:
        return 400, {
            "message": "Error with pagination parameters. Please try different values."
        }

    try:
        article_ids = [article.id for article in paginated_articles]

        review_ratings = {
            item["article_id"]: round(item["avg_rating"] or 0, 1)
            for item in Review.objects.filter(article_id__in=article_ids)
            .values("article_id")
            .annotate(avg_rating=Avg("rating"))
        }

        response_data = PaginatedArticlesListResponse(
            items=[
                ArticlesListOut.from_orm_with_fields(
                    article=article,
                    total_ratings=review_ratings.get(article.id, 0),
                    community_article=None,
                )
                for article in paginated_articles
            ],
            total=paginator.count,
            page=page,
            per_page=per_page,
            num_pages=paginator.num_pages,
        )

        return 200, response_data
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/my-communities",
    response={
        200: PaginatedCommunities,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    summary="Get My Communities",
    auth=JWTAuth(),
)
def list_my_communities(
    request: HttpRequest,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
):
    try:
        user = request.auth
        try:
            communities = Community.objects.filter(admins__in=[user])
        except Exception:
            return 500, {"message": "Error retrieving communities. Please try again."}

        # Apply search if provided
        try:
            if search:
                search = search.strip()
                if len(search) > 0:
                    communities = communities.filter(admins__in=[user]).filter(
                        Q(name__icontains=search) | Q(description__icontains=search)
                    )
        except Exception:
            return 500, {"message": "Error processing search query. Please try again."}

        # Apply sorting
        try:
            if sort:
                sort = sort.strip()
                if sort == "latest":
                    communities = communities.order_by("-created_at")
                elif sort == "oldest":
                    communities = communities.order_by("created_at")
                elif sort == "name_asc":
                    communities = communities.order_by("name")
                elif sort == "name_desc":
                    communities = communities.order_by("-name")
                # Add more sorting options if needed
            else:
                # Default sort by latest
                communities = communities.order_by("-created_at")
        except Exception:
            return 500, {"message": "Error sorting communities. Please try again."}

        try:
            paginator = Paginator(communities, per_page)
            paginated_communities = paginator.get_page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        try:
            # results = [
            #     CommunityListOut.from_orm_with_custom_fields(community, user=user)
            #     for community in paginated_communities.object_list
            # ]

            # return 200, PaginatedCommunities(
            #     items=results,
            #     total=paginator.count,
            #     page=page,
            #     per_page=per_page,
            #     num_pages=paginator.num_pages,
            # )
            community_ids = [
                community.id for community in paginated_communities.object_list
            ]

            # Bulk counts for published articles
            articles_count = dict(
                CommunityArticle.objects.filter(
                    community_id__in=community_ids, status="published"
                )
                .values("community_id")
                .annotate(count=Count("id"))
                .values_list("community_id", "count")
            )

            # Bulk counts for members
            members_count = dict(
                Membership.objects.filter(community_id__in=community_ids)
                .values("community_id")
                .annotate(count=Count("id"))
                .values_list("community_id", "count")
            )

            # Prepare response
            results = []
            for community in paginated_communities.object_list:
                results.append(
                    CommunityListOut(
                        id=community.id,
                        name=community.name,
                        description=community.description,
                        type=community.type,
                        slug=community.slug,
                        created_at=community.created_at,
                        num_members=members_count.get(community.id, 0),
                        num_published_articles=articles_count.get(community.id, 0),
                    )
                )

            return 200, PaginatedCommunities(
                items=results,
                total=paginator.count,
                page=page,
                per_page=per_page,
                num_pages=paginator.num_pages,
            )
        except Exception:
            return 500, {
                "message": "Error formatting community data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/contributed-communities",
    response={200: List[UserCommunitySchema], codes_4xx: Message, codes_5xx: Message},
    summary="Get Contributed Communities",
    auth=JWTAuth(),
)
def get_my_communities(request):
    try:
        user = request.auth
        communities = []

        try:
            # Get communities where the user is an admin
            admin_communities = user.admin_communities.annotate(
                members_count=Count("members")
            )
            for community in admin_communities:
                communities.append(
                    {
                        "name": community.name,
                        "role": "Admin",
                        "members_count": community.members_count,
                    }
                )
        except Exception:
            return 500, {
                "message": "Error retrieving admin communities. Please try again."
            }

        try:
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
        except Exception:
            return 500, {
                "message": "Error retrieving reviewer communities. Please try again."
            }

        try:
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
        except Exception:
            return 500, {
                "message": "Error retrieving moderator communities. Please try again."
            }

        try:
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
        except Exception:
            return 500, {
                "message": "Error retrieving member communities. Please try again."
            }

        return 200, communities
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/contributed-posts",
    response={200: List[UserPostSchema], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_my_posts(request):
    try:
        user = request.auth
        try:
            posts = Post.objects.filter(author=user, is_deleted=False).order_by(
                "-created_at"
            )
        except Exception:
            return 500, {"message": "Error retrieving your posts. Please try again."}

        try:
            post_content_type = ContentType.objects.get_for_model(Post)
        except Exception:
            return 500, {"message": "Error setting up content types. Please try again."}

        result = []
        for post in posts:
            try:
                likes_count = Reaction.objects.filter(
                    content_type=post_content_type,
                    object_id=post.id,
                    vote=Reaction.LIKE,
                ).count()

                # Determine the most recent action (creation or comment)
                latest_comment = (
                    post.post_comments.filter(is_deleted=False)
                    .order_by("-created_at")
                    .first()
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
            except Exception:
                # Skip posts with errors instead of failing entirely
                continue

        return 200, result
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/my-favorites",
    response={200: List[FavoriteItemSchema], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_my_favorites(request):
    try:
        user = request.auth
        favorites = []

        try:
            # Get content types
            article_type = ContentType.objects.get_for_model(Article)
            community_type = ContentType.objects.get_for_model(Community)
            post_type = ContentType.objects.get_for_model(Post)
        except Exception:
            return 500, {"message": "Error setting up content types. Please try again."}

        try:
            # Get user's liked items
            liked_items = Reaction.objects.filter(user=user, vote=Reaction.LIKE)
        except Exception:
            return 500, {
                "message": "Error retrieving your favorite items. Please try again."
            }

        for item in liked_items:
            try:
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
            except Exception:
                # Skip items with errors instead of failing entirely
                continue

        return 200, favorites
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/bookmarks",
    response={200: List[BookmarkSchema], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_my_bookmarks(request):
    try:
        user = request.auth
        try:
            bookmarks = Bookmark.objects.filter(user=user).select_related(
                "content_type"
            )
        except Exception:
            return 500, {
                "message": "Error retrieving your bookmarks. Please try again."
            }

        result = []
        for bookmark in bookmarks:
            try:
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
            except Exception:
                # Skip bookmarks with errors instead of failing entirely
                continue

        return 200, result
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


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
    try:
        try:
            user_notifications = Notification.objects.filter(user=request.auth)
        except Exception:
            return 500, {
                "message": "Error retrieving your notifications. Please try again."
            }

        try:
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
        except Exception:
            return 500, {"message": "Error filtering notifications. Please try again."}

        try:
            user_notifications = user_notifications.order_by("-created_at")
        except Exception:
            return 500, {"message": "Error sorting notifications. Please try again."}

        try:
            notifications_list = [
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
            return 200, notifications_list
        except Exception:
            return 500, {
                "message": "Error formatting notification data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/notifications/{notification_id}/mark-as-read",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def mark_notification_as_read(request, notification_id: int):
    try:
        try:
            notification = Notification.objects.get(
                pk=notification_id, user=request.auth
            )
        except Notification.DoesNotExist:
            return 404, {"message": "Notification not found."}
        except Exception:
            return 500, {"message": "Error retrieving notification. Please try again."}

        if not notification.is_read:
            try:
                notification.is_read = True
                notification.save()
                return 200, {"message": "Notification marked as read."}
            except Exception:
                return 500, {
                    "message": "Error updating notification status. Please try again."
                }
        else:
            return 200, {"message": "Notification was already marked as read."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}
