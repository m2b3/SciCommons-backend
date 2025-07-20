import logging
from typing import List, Optional

from django.core.paginator import Paginator
from django.db import transaction
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, Discussion, DiscussionComment, Reaction
from articles.schemas import (
    CreateDiscussionSchema,
    DiscussionCommentCreateSchema,
    DiscussionCommentOut,
    DiscussionCommentUpdateSchema,
    DiscussionOut,
    PaginatedDiscussionSchema,
)
from communities.models import Community, CommunityArticle
from myapp.schemas import Message
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Discussions"])
logger = logging.getLogger(__name__)

"""
Article discussions API
"""


@router.post(
    "/{article_id}/discussions/",
    response={201: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_discussion(
    request,
    article_id: int,
    discussion_data: CreateDiscussionSchema,
    community_id: Optional[int] = None,
):
    try:
        with transaction.atomic():
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return 404, {"message": "Article not found."}
            except Exception:
                return 500, {"message": "Error retrieving article. Please try again."}

            user = request.auth

            community = None
            is_pseudonymous = False
            if community_id:
                try:
                    community = Community.objects.get(id=community_id)
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}
                except Exception:
                    return 500, {
                        "message": "Error retrieving community. Please try again."
                    }

                if not community.is_member(user):
                    return 403, {"message": "You are not a member of this community."}

                try:
                    community_article = CommunityArticle.objects.get(
                        article=article, community=community
                    )
                    if community_article.is_pseudonymous:
                        is_pseudonymous = True
                except CommunityArticle.DoesNotExist:
                    return 404, {"message": "Article not found in this community."}
                except Exception:
                    return 500, {
                        "message": "Error retrieving community article. Please try again."
                    }

            try:
                discussion = Discussion.objects.create(
                    article=article,
                    author=user,
                    community=community,
                    topic=discussion_data.topic,
                    content=discussion_data.content,
                    is_pseudonymous=is_pseudonymous,
                )
            except Exception:
                return 500, {"message": "Error creating discussion. Please try again."}

            if is_pseudonymous:
                try:
                    # Create an anonymous name for the user who created the review
                    discussion.get_anonymous_name()
                except Exception:
                    logger.error(
                        "Error creating anonymous name for discussion", exc_info=True
                    )
                    # Continue even if anonymous name creation fails

        try:
            return 201, DiscussionOut.from_orm(discussion, user)
        except Exception:
            return 500, {
                "message": "Discussion created but error retrieving discussion data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{article_id}/discussions/",
    response={200: PaginatedDiscussionSchema, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_discussions(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    try:
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        if community_id:
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            except Exception:
                return 500, {"message": "Error retrieving community. Please try again."}

            # if the community is hidden, only members can view reviews
            if not community.is_member(request.auth) and community.type == "hidden":
                return 403, {"message": "You are not a member of this community."}

            try:
                # discussions = discussions.filter(community=community)
                discussions = Discussion.objects.filter(
                    article=article, community=community
                ).order_by("-created_at")
            except Exception:
                return 500, {
                    "message": "Error retrieving community discussions. Please try again."
                }
        else:
            try:
                discussions = Discussion.objects.filter(
                    article=article, community=None
                ).order_by("-created_at")
            except Exception:
                return 500, {
                    "message": "Error retrieving discussions. Please try again."
                }

        try:
            paginator = Paginator(discussions, size)
            page_obj = paginator.page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        current_user: Optional[User] = None if not request.auth else request.auth

        try:
            items = [
                DiscussionOut.from_orm(discussion, current_user)
                for discussion in page_obj.object_list
            ]

            response_data = PaginatedDiscussionSchema(
                items=items, total=paginator.count, page=page, per_page=size
            )

            return 200, response_data
        except Exception:
            return 500, {
                "message": "Error formatting discussion data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/{discussion_id}/",
    response={200: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_discussion(request, discussion_id: int):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception:
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            response_data = DiscussionOut.from_orm(discussion, user)
            return 200, response_data
        except Exception:
            return 500, {
                "message": "Error formatting discussion data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/discussions/{discussion_id}/",
    response={201: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_discussion(
    request, discussion_id: int, discussion_data: CreateDiscussionSchema
):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception:
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth

        # Check if the review belongs to the user
        if discussion.author != user:
            return 403, {
                "message": "You do not have permission to update this discussion."
            }

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            # Update the review with new data if provided
            discussion.topic = discussion_data.topic or discussion.topic
            discussion.content = discussion_data.content or discussion.content
            discussion.save()
        except Exception:
            return 500, {"message": "Error updating discussion. Please try again."}

        try:
            response_data = DiscussionOut.from_orm(discussion, user)
            return 201, response_data
        except Exception:
            return 500, {
                "message": "Discussion updated but error retrieving discussion data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/{discussion_id}/",
    response={201: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_discussion(request, discussion_id: int):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception:
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth  # Assuming user is authenticated

        if discussion.author != user:
            return 403, {
                "message": "You do not have permission to delete this discussion."
            }

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            discussion.topic = "[deleted]"
            discussion.content = "[deleted]"
            discussion.save()
        except Exception:
            return 500, {"message": "Error deleting discussion. Please try again."}

        return 201, {"message": "Discussion deleted successfully."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Endpoints for comments on discussions
"""


# Create a Comment
@router.post(
    "/discussions/{discussion_id}/comments/",
    response={201: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_comment(request, discussion_id: int, payload: DiscussionCommentCreateSchema):
    try:
        try:
            user = request.auth
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception:
            return 500, {"message": "Error retrieving discussion. Please try again."}

        is_pseudonymous = False

        if discussion.community:
            try:
                if not discussion.community.is_member(user):
                    return 403, {"message": "You are not a member of this community."}

                community_article = CommunityArticle.objects.get(
                    article=discussion.article, community=discussion.community
                )
                if community_article.is_pseudonymous:
                    is_pseudonymous = True
            except CommunityArticle.DoesNotExist:
                return 404, {"message": "Article not found in this community."}
            except Exception:
                return 500, {
                    "message": "Error checking community membership. Please try again."
                }

        parent_comment = None

        if payload.parent_id:
            try:
                parent_comment = DiscussionComment.objects.get(id=payload.parent_id)

                if parent_comment.parent and parent_comment.parent.parent:
                    return 400, {
                        "message": "Exceeded maximum comment nesting level of 3"
                    }
            except DiscussionComment.DoesNotExist:
                return 404, {"message": "Parent comment not found."}
            except Exception:
                return 500, {
                    "message": "Error retrieving parent comment. Please try again."
                }

        try:
            comment = DiscussionComment.objects.create(
                discussion=discussion,
                community=discussion.community,
                author=user,
                content=payload.content,
                parent=parent_comment,
                is_pseudonymous=is_pseudonymous,
            )
        except Exception:
            return 500, {"message": "Error creating comment. Please try again."}

        if is_pseudonymous:
            try:
                # Create an anonymous name for the user who created the comment
                comment.get_anonymous_name()
            except Exception:
                logger.error("Error creating anonymous name for comment", exc_info=True)
                # Continue even if anonymous name creation fails

        # Return comment with replies
        try:
            return 201, DiscussionCommentOut.from_orm_with_replies(comment, user)
        except Exception:
            return 500, {
                "message": "Comment created but error retrieving comment data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get a Comment
@router.get(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    try:
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            comment.discussion.community
            and not comment.discussion.community.is_member(current_user)
            and comment.discussion.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, DiscussionCommentOut.from_orm_with_replies(
                comment, current_user
            )
        except Exception:
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/{discussion_id}/comments/",
    response={200: List[DiscussionCommentOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_discussion_comments(
    request, discussion_id: int, page: int = 1, size: int = 10
):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception:
            return 500, {"message": "Error retrieving discussion. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            discussion.community
            and not discussion.community.is_member(current_user)
            and discussion.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            comments = (
                DiscussionComment.objects.filter(discussion=discussion, parent=None)
                .select_related("author")
                .order_by("-created_at")
            )
        except Exception:
            return 500, {"message": "Error retrieving comments. Please try again."}

        try:
            return 200, [
                DiscussionCommentOut.from_orm_with_replies(comment, current_user)
                for comment in comments
            ]
        except Exception:
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: DiscussionCommentUpdateSchema):
    try:
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        if comment.author != request.auth:
            return 403, {
                "message": "You do not have permission to update this comment."
            }

        if comment.discussion.community and not comment.discussion.community.is_member(
            request.auth
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            comment.content = payload.content or comment.content
            comment.save()
        except Exception:
            return 500, {"message": "Error updating comment. Please try again."}

        try:
            return 200, DiscussionCommentOut.from_orm_with_replies(
                comment, request.auth
            )
        except Exception:
            return 500, {
                "message": "Comment updated but error retrieving comment data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/comments/{comment_id}/",
    response={204: None, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_comment(request, comment_id: int):
    try:
        user = request.auth
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        # Check if the user is the owner of the comment or has permission to delete it
        if comment.author != user:
            return 403, {
                "message": "You do not have permission to delete this comment."
            }

        try:
            # Delete reactions associated with the comment
            Reaction.objects.filter(
                content_type__model="discussioncomment", object_id=comment.id
            ).delete()

            # Logically delete the comment by clearing its content and marking it as deleted
            comment.content = "[deleted]"
            comment.is_deleted = True
            comment.save()
        except Exception:
            return 500, {"message": "Error deleting comment. Please try again."}

        return 204, None
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}
