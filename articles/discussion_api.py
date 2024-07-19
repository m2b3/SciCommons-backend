from typing import Optional

from django.core.paginator import Paginator
from ninja import Router
from ninja.responses import codes_4xx

from articles.models import Article, Discussion, DiscussionComment, Reaction
from articles.schemas import (
    CreateDiscussionSchema,
    DiscussionCommentCreateSchema,
    DiscussionCommentOut,
    DiscussionCommentUpdateSchema,
    DiscussionOut,
    PaginatedDiscussionSchema,
)
from communities.models import Community
from myapp.schemas import Message
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Discussions"])


"""
Article discussions API
"""


@router.post(
    "/{article_id}/discussions/",
    response={201: DiscussionOut, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def create_discussion(
    request,
    article_id: int,
    discussion_data: CreateDiscussionSchema,
    community_id: Optional[int] = None,
):
    article = Article.objects.get(id=article_id)
    user = request.auth

    community = None

    if community_id:
        community = Community.objects.get(id=community_id)
        if not community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

    discussion = Discussion.objects.create(
        article=article,
        author=user,
        community=community,
        topic=discussion_data.topic,
        content=discussion_data.content,
    )

    # Create an anonymous name for the user who created the review
    discussion.get_anonymous_name()

    return 201, DiscussionOut.from_orm(discussion, user)


@router.get(
    "/{article_id}/discussions/",
    response={200: PaginatedDiscussionSchema, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def list_discussions(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    article = Article.objects.get(id=article_id)
    discussions = Discussion.objects.filter(article=article).order_by("-created_at")

    if community_id:
        community = Community.objects.get(id=community_id)
        # if the community is hidden, only members can view reviews
        if not community.is_member(request.auth) and community.type == "hidden":
            return 403, {"message": "You are not a member of this community."}

        discussions = discussions.filter(community=community)
    else:
        discussions = discussions.filter(community=None)

    paginator = Paginator(discussions, size)
    page_obj = paginator.page(page)
    current_user: Optional[User] = None if not request.auth else request.auth

    items = [
        DiscussionOut.from_orm(review, current_user) for review in page_obj.object_list
    ]

    return PaginatedDiscussionSchema(
        items=items, total=paginator.count, page=page, per_page=size
    )


@router.get(
    "/discussions/{discussion_id}/",
    response={200: DiscussionOut, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def get_discussion(request, discussion_id: int):
    discussion = Discussion.objects.get(id=discussion_id)
    user = request.auth

    if discussion.community and not discussion.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    return 200, DiscussionOut.from_orm(discussion, user)


@router.put(
    "/discussions/{discussion_id}/",
    response={201: DiscussionOut, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def update_discussion(
    request, discussion_id: int, discussion_data: CreateDiscussionSchema
):
    discussion = Discussion.objects.get(id=discussion_id)
    user = request.auth

    # Check if the review belongs to the user
    if discussion.author != user:
        return 403, {"message": "You do not have permission to update this review."}

    if discussion.community and not discussion.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    # Update the review with new data if provided
    discussion.topic = discussion_data.topic or discussion.topic
    discussion.content = discussion_data.content or discussion.content
    discussion.save()

    return 201, DiscussionOut.from_orm(discussion, user)


@router.delete(
    "/discussions/{discussion_id}/",
    response={201: Message, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_discussion(request, discussion_id: int):
    discussion = Discussion.objects.get(id=discussion_id)
    user = request.auth  # Assuming user is authenticated

    if discussion.author != user:
        return 403, {"message": "You do not have permission to delete this review."}

    if discussion.community and not discussion.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    discussion.topic = "[deleted]"
    discussion.content = "[deleted]"
    discussion.save()

    return 201, {"message": "Discussion deleted successfully."}


"""
Endpoints for comments on discussions
"""


# Create a Comment
@router.post(
    "/discussions/{discussion_id}/comments/",
    response={201: DiscussionCommentOut, 400: Message, 403: Message},
    auth=JWTAuth(),
)
def create_comment(request, discussion_id: int, payload: DiscussionCommentCreateSchema):
    user = request.auth
    discussion = Discussion.objects.get(id=discussion_id)

    if discussion.community and not discussion.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    parent_comment = None

    if payload.parent_id:
        parent_comment = DiscussionComment.objects.get(id=payload.parent_id)

        if parent_comment.parent and parent_comment.parent.parent:
            return 400, {"message": "Exceeded maximum comment nesting level of 3"}

    comment = DiscussionComment.objects.create(
        discussion=discussion,
        community=discussion.community,
        author=user,
        content=payload.content,
        parent=parent_comment,
    )
    # Create an anonymous name for the user who created the comment
    comment.get_anonymous_name()

    # Return comment with replies
    return 201, DiscussionCommentOut.from_orm_with_replies(comment, user)


# Get a Comment
@router.get(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, 404: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    comment = DiscussionComment.objects.get(id=comment_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        comment.community
        and not comment.community.is_member(current_user)
        and comment.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    return 200, DiscussionCommentOut.from_orm_with_replies(comment, current_user)


@router.get(
    "/discussions/{discussion_id}/comments/",
    response={200: PaginatedDiscussionSchema, 404: Message},
    auth=OptionalJWTAuth,
)
def list_discussion_comments(
    request, discussion_id: int, page: int = 1, size: int = 10
):
    discussion = Discussion.objects.get(id=discussion_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        discussion.community
        and not discussion.community.is_member(current_user)
        and discussion.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    comments = (
        DiscussionComment.objects.filter(discussion=discussion)
        .select_related("author")
        .order_by("-created_at")
    )

    return [
        DiscussionCommentOut.from_orm_with_replies(comment, current_user)
        for comment in comments
    ]


@router.put(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, 403: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: DiscussionCommentUpdateSchema):
    comment = DiscussionComment.objects.get(id=comment_id)

    if comment.author != request.auth:
        return 403, {"message": "You do not have permission to update this comment."}

    if comment.community and not comment.community.is_member(request.auth):
        return 403, {"message": "You are not a member of this community."}

    comment.content = payload.content or comment.content

    comment.save()

    return 200, DiscussionCommentOut.from_orm_with_replies(comment, request.auth)


@router.delete(
    "/discussions/comments/{comment_id}/",
    response={204: None, 403: Message},
    auth=JWTAuth(),
)
def delete_comment(request, comment_id: int):
    user = request.auth
    comment = DiscussionComment.objects.get(id=comment_id)

    # Check if the user is the owner of the comment or has permission to delete it
    if comment.author != user:
        return 403, {"message": "You do not have permission to delete this comment."}

    # Delete reactions associated with the comment
    Reaction.objects.filter(
        content_type__model="discussioncomment", object_id=comment.id
    ).delete()

    # Logically delete the comment by clearing its content and marking it as deleted
    comment.content = "[deleted]"
    comment.is_deleted = True
    comment.save()

    return 204, None
