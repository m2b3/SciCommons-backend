"""
A common API for HashTags, Reactions, and Bookmarks
"""

import logging
from typing import Literal, Optional
from urllib.parse import unquote

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count
from ninja import Query, Router
from ninja.errors import HttpRequest
from ninja.responses import codes_4xx, codes_5xx

# Todo: Move the Reaction model to the users app
from articles.models import Article, Reaction
from communities.models import Community
from myapp.schemas import Message, PermissionCheckOut
from posts.models import Post
from posts.schemas import PaginatedPostsResponse, PostOut
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Bookmark, Hashtag, HashtagRelation, User
from users.schemas import (
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

# Module-level logger
logger = logging.getLogger(__name__)

"""
Check Permissions
"""


@router.get(
    "/check-permission",
    response={200: PermissionCheckOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def check_permission(
    request,
    dashboard_type: Optional[Literal["article", "community"]] = Query(None),
    resource_id: Optional[str] = Query(None),
):
    try:
        user = request.auth
        if not user:
            return 200, {"has_permission": False}

        if not dashboard_type or not resource_id:
            return 200, {"has_permission": False}

        try:
            if resource_id:
                resource_id = unquote(resource_id)
        except Exception:
            return 400, {
                "message": "Invalid resource ID format. Please check and try again."
            }

        try:
            if dashboard_type == "article":
                try:
                    article = Article.objects.get(slug=resource_id)
                    has_permission = article.submitter == user
                except Article.DoesNotExist:
                    return 404, {"message": "Article not found."}
                except Exception as e:
                    logger.error(f"Error retrieving article: {e}")
                    return 500, {
                        "message": "Error retrieving article. Please try again."
                    }
            elif dashboard_type == "community":
                try:
                    community = Community.objects.get(name=resource_id)
                    has_permission = community.is_admin(user)
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}
                except Exception as e:
                    logger.error(f"Error retrieving community: {e}")
                    return 500, {
                        "message": "Error retrieving community. Please try again."
                    }
            else:
                has_permission = False

            return 200, {"has_permission": has_permission}
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return 500, {"message": "Error checking permissions. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Bookmarks API
"""


def get_content_type(content_type_value: str) -> ContentType:
    try:
        app_label, model = content_type_value.split(".")
        return ContentType.objects.get(app_label=app_label, model=model)
    except ValueError:
        raise ValueError("Invalid content type format. Must be 'app_label.model'")
    except ContentType.DoesNotExist:
        raise ContentType.DoesNotExist(
            f"Content type {content_type_value} does not exist"
        )
    except Exception as e:
        raise Exception(f"Error retrieving content type: {str(e)}")


@router.post(
    "/toggle-bookmark",
    response={
        200: BookmarkToggleResponseSchema,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def toggle_bookmark(request, data: BookmarkToggleSchema):
    try:
        user = request.auth

        try:
            content_type = get_content_type(data.content_type.value)
        except ValueError:
            return 400, {
                "message": "Invalid content type format. Please check and try again."
            }
        except ContentType.DoesNotExist:
            return 400, {
                "message": "Content type does not exist. Please check and try again."
            }
        except Exception as e:
            logger.error(f"Error retrieving content type: {e}")
            return 500, {"message": "Error retrieving content type. Please try again."}

        try:
            bookmark, created = Bookmark.objects.get_or_create(
                user=user, content_type=content_type, object_id=data.object_id
            )
        except Exception as e:
            logger.error(f"Error processing bookmark operation: {e}")
            return 500, {
                "message": "Error processing bookmark operation. Please try again."
            }

        if created:
            return 200, {
                "message": "Bookmark added successfully",
                "is_bookmarked": True,
            }
        else:
            try:
                bookmark.delete()
                return 200, {
                    "message": "Bookmark removed successfully",
                    "is_bookmarked": False,
                }
            except Exception as e:
                logger.error(f"Error removing bookmark: {e}")
                return 500, {"message": "Error removing bookmark. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/bookmark-status/{content_type}/{object_id}",
    response={
        200: BookmarkStatusResponseSchema,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=OptionalJWTAuth,
)
def get_bookmark_status(request, content_type: ContentTypeEnum, object_id: int):
    try:
        user: Optional[User] = None if not request.auth else request.auth

        if not user:
            return 200, {"is_bookmarked": None}

        try:
            content_type_obj = get_content_type(content_type.value)
        except ValueError:
            return 400, {
                "message": "Invalid content type format. Please check and try again."
            }
        except ContentType.DoesNotExist:
            return 400, {
                "message": "Content type does not exist. Please check and try again."
            }
        except Exception as e:
            logger.error(f"Error retrieving content type: {e}")
            return 500, {"message": "Error retrieving content type. Please try again."}

        try:
            is_bookmarked = Bookmark.objects.filter(
                user=user, content_type=content_type_obj, object_id=object_id
            ).exists()
            return 200, {"is_bookmarked": is_bookmarked}
        except Exception as e:
            logger.error(f"Error checking bookmark status: {e}")
            return 500, {"message": "Error checking bookmark status. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Reaction API (Like/Dislike)
"""


@router.post(
    "/reactions",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def post_reaction(request, reaction: ReactionIn):
    try:
        try:
            content_type = get_content_type(reaction.content_type.value)
        except ValueError:
            return 400, {
                "message": "Invalid content type format. Please check and try again."
            }
        except ContentType.DoesNotExist:
            return 400, {
                "message": "Content type does not exist. Please check and try again."
            }
        except Exception as e:
            logger.error(f"Error retrieving content type: {e}")
            return 500, {"message": "Error retrieving content type. Please try again."}

        try:
            existing_reaction = Reaction.objects.filter(
                user=request.auth,
                content_type=content_type,
                object_id=reaction.object_id,
            ).first()
        except Exception as e:
            logger.error(f"Error checking existing reactions: {e}")
            return 500, {
                "message": "Error checking existing reactions. Please try again."
            }

        if existing_reaction:
            if existing_reaction.vote == reaction.vote.value:
                # User is clicking the same reaction type, so remove it
                try:
                    existing_reaction.delete()
                    return 200, ReactionOut(
                        id=None,
                        user_id=request.auth.id,
                        vote=None,
                        created_at=None,
                        message="Reaction removed",
                    )
                except Exception as e:
                    logger.error(f"Error removing reaction: {e}")
                    return 500, {
                        "message": "Error removing reaction. Please try again."
                    }
            else:
                # User is changing their reaction from like to dislike or vice versa
                try:
                    existing_reaction.vote = reaction.vote.value
                    existing_reaction.save()
                    return 200, ReactionOut(
                        id=existing_reaction.id,
                        user_id=existing_reaction.user_id,
                        vote=VoteEnum(existing_reaction.vote),
                        created_at=existing_reaction.created_at.isoformat(),
                        message="Reaction updated",
                    )
                except Exception as e:
                    logger.error(f"Error updating reaction: {e}")
                    return 500, {
                        "message": "Error updating reaction. Please try again."
                    }
        else:
            # User is reacting for the first time
            try:
                new_reaction = Reaction.objects.create(
                    user=request.auth,
                    content_type=content_type,
                    object_id=reaction.object_id,
                    vote=reaction.vote.value,
                )
                return 200, ReactionOut(
                    id=new_reaction.id,
                    user_id=new_reaction.user_id,
                    vote=VoteEnum(new_reaction.vote),
                    created_at=new_reaction.created_at.isoformat(),
                    message="Reaction added",
                )
            except Exception as e:
                logger.error(f"Error adding reaction: {e}")
                return 500, {"message": "Error adding reaction. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/reaction_count/{content_type}/{object_id}/",
    response={200: ReactionCountOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_reaction_count(request, content_type: ContentTypeEnum, object_id: int):
    try:
        try:
            content_type = get_content_type(content_type.value)
        except ValueError:
            return 400, {
                "message": "Invalid content type format. Please check and try again."
            }
        except ContentType.DoesNotExist:
            return 400, {
                "message": "Content type does not exist. Please check and try again."
            }
        except Exception as e:
            logger.error(f"Error retrieving content type: {e}")
            return 500, {"message": "Error retrieving content type. Please try again."}

        try:
            reactions = Reaction.objects.filter(
                content_type=content_type, object_id=object_id
            )
        except Exception as e:
            logger.error(f"Error retrieving reactions: {e}")
            return 500, {"message": "Error retrieving reactions. Please try again."}

        try:
            likes = reactions.filter(vote=VoteEnum.LIKE.value).count()
            dislikes = reactions.filter(vote=VoteEnum.DISLIKE.value).count()
        except Exception as e:
            logger.error(f"Error counting reactions: {e}")
            return 500, {"message": "Error counting reactions. Please try again."}

        # Check if the authenticated user is the author
        current_user: Optional[User] = None if not request.auth else request.auth
        user_reaction = None

        if current_user:
            try:
                user_reaction_obj = reactions.filter(user=current_user).first()
                if user_reaction_obj:
                    user_reaction = VoteEnum(user_reaction_obj.vote)
            except Exception as e:
                logger.error(f"Error retrieving user's reaction: {e}")
                # Continue even if we can't get user's reaction
                pass

        return 200, ReactionCountOut(
            likes=likes,
            dislikes=dislikes,
            user_reaction=user_reaction,
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Hashtags API
"""


@router.get(
    "/hashtags/",
    response={200: PaginatedHashtagOut, codes_4xx: Message, codes_5xx: Message},
)
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
    try:
        try:
            hashtags = Hashtag.objects.annotate(count=Count("hashtagrelation"))
        except Exception as e:
            logger.error(f"Error retrieving hashtags: {e}")
            return 500, {"message": "Error retrieving hashtags. Please try again."}

        try:
            if search:
                hashtags = hashtags.filter(name__icontains=search)
        except Exception as e:
            logger.error(f"Error searching hashtags: {e}")
            return 500, {"message": "Error searching hashtags. Please try again."}

        try:
            if sort == SortEnum.POPULAR:
                hashtags = hashtags.order_by("-count", "name")
            elif sort == SortEnum.RECENT:
                hashtags = hashtags.order_by("-id")
            else:  # ALPHABETICAL
                hashtags = hashtags.order_by("name")
        except Exception as e:
            logger.error(f"Error sorting hashtags: {e}")
            return 500, {"message": "Error sorting hashtags. Please try again."}

        try:
            paginator = Paginator(hashtags, per_page)
            page_obj = paginator.get_page(page)
        except Exception as e:
            logger.error(f"Error paginating hashtags: {e}")
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        try:
            return 200, PaginatedHashtagOut(
                items=[
                    HashtagOut(name=h.name, count=h.count) for h in page_obj.object_list
                ],
                total=paginator.count,
                page=page_obj.number,
                per_page=per_page,
                pages=paginator.num_pages,
            )
        except Exception as e:
            logger.error(f"Error formatting hashtag data: {e}")
            return 500, {"message": "Error formatting hashtag data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Todo: Delete this API endpoint
@router.get(
    "/my-posts",
    response={200: PaginatedPostsResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def list_my_posts(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at", enum=["created_at", "title"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    hashtag: Optional[str] = Query(None),
):
    try:
        user = request.auth

        try:
            posts = Post.objects.filter(author=user, is_deleted=False)
        except Exception as e:
            logger.error(f"Error retrieving your posts: {e}")
            return 500, {"message": "Error retrieving your posts. Please try again."}

        # Apply hashtag filtering
        if hashtag:
            try:
                hashtag_id = (
                    Hashtag.objects.filter(name=hashtag)
                    .values_list("id", flat=True)
                    .first()
                )
                if hashtag_id:
                    post_ids = HashtagRelation.objects.filter(
                        hashtag_id=hashtag_id,
                        content_type=ContentType.objects.get_for_model(Post),
                    ).values_list("object_id", flat=True)
                    posts = posts.filter(id__in=post_ids)
            except Exception as e:
                logger.error(f"Error filtering posts by hashtag: {e}")
                return 500, {
                    "message": "Error filtering posts by hashtag. Please try again."
                }

        try:
            # Todo: Add Filter for sorting by post reactions
            # Apply sorting
            order_prefix = "-" if sort_order == "desc" else ""
            posts = posts.order_by(f"{order_prefix}{sort_by}")
        except Exception as e:
            logger.error(f"Error sorting posts: {e}")
            return 500, {"message": "Error sorting posts. Please try again."}

        try:
            paginator = Paginator(posts, size)
            page_obj = paginator.get_page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        try:
            return 200, PaginatedPostsResponse(
                items=[PostOut.resolve_post(post, user) for post in page_obj],
                total=paginator.count,
                page=page,
                size=size,
            )
        except Exception as e:
            logger.error(f"Error formatting post data: {e}")
            return 500, {"message": "Error formatting post data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
