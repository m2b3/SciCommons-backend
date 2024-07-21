from typing import List, Optional

from django.core.paginator import Paginator
from django.utils import timezone
from ninja import Router
from ninja.responses import codes_4xx

from articles.models import Article, Reaction, Review, ReviewComment
from articles.schemas import (
    CreateReviewSchema,
    Message,
    PaginatedReviewSchema,
    ReviewCommentCreateSchema,
    ReviewCommentOut,
    ReviewCommentUpdateSchema,
    ReviewOut,
    ReviewUpdateSchema,
)
from communities.models import Community
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Reviews"])


@router.post(
    "/{article_id}/reviews/",
    response={201: ReviewOut, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def create_review(
    request,
    article_id: int,
    review_data: CreateReviewSchema,
    community_id: Optional[int] = None,
):
    article = Article.objects.get(id=article_id)
    user = request.auth

    # Ensure the owner of the article can't review their own article
    if article.submitter == user:
        return 400, {"message": "You can't review your own article."}

    # Check if the user has already reviewed the article in the same context
    existing_review = Review.objects.filter(article=article, user=user)

    if community_id:
        community = Community.objects.get(id=community_id)
        if not community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        if existing_review.filter(community=community).exists():
            return 400, {
                "message": "You have already reviewed this article in this community."
            }
    else:
        if existing_review.filter(community__isnull=True).exists():
            return 400, {
                "message": "You have already reviewed this article on\
                      the official public page."
            }

    review = Review.objects.create(
        article=article,
        user=user,
        community=community if community_id else None,
        rating=review_data.rating,
        subject=review_data.subject,
        content=review_data.content,
    )
    # Create an anonymous name for the user who created the review
    review.get_anonymous_name()

    return 201, ReviewOut.from_orm(review, user)


@router.get(
    "/{article_id}/reviews/",
    response={200: PaginatedReviewSchema, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def list_reviews(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    article = Article.objects.get(id=article_id)
    reviews = Review.objects.filter(article=article).order_by("-created_at")

    if community_id:
        community = Community.objects.get(id=community_id)
        # if the community is hidden, only members can view reviews
        if not community.is_member(request.auth) and community.type == "hidden":
            return 403, {"message": "You are not a member of this community."}

        reviews = reviews.filter(community=community)
    else:
        reviews = reviews.filter(community=None)

    paginator = Paginator(reviews, size)
    page_obj = paginator.page(page)
    current_user: Optional[User] = None if not request.auth else request.auth

    items = [
        ReviewOut.from_orm(review, current_user) for review in page_obj.object_list
    ]

    return PaginatedReviewSchema(
        items=items, total=paginator.count, page=page, size=size
    )


@router.get(
    "/reviews/{review_id}/",
    response={200: ReviewOut, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def get_review(request, review_id: int):
    review = Review.objects.get(id=review_id)
    user = request.auth

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    return 200, ReviewOut.from_orm(review, user)


@router.put(
    "/reviews/{review_id}/",
    response={201: ReviewOut, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def update_review(request, review_id: int, review_data: ReviewUpdateSchema):
    review = Review.objects.get(id=review_id)
    user = request.auth

    # Check if the review belongs to the user
    if review.user != user:
        return 403, {"message": "You do not have permission to update this review."}

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    # Update the review with new data if provided
    review.rating = review_data.rating or review.rating
    review.subject = review_data.subject or review.subject
    review.content = review_data.content or review.content
    review.save()

    return 201, ReviewOut.from_orm(review, user)


@router.delete(
    "/reviews/{review_id}/",
    response={201: Message, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    review = Review.objects.get(id=review_id)
    user = request.auth  # Assuming user is authenticated

    if review.user != user:
        return 403, {"message": "You do not have permission to delete this review."}

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    review.subject = "[deleted]"
    review.content = "[deleted]"
    review.deleted_at = timezone.now()

    return 201, {"message": "Review deleted successfully."}


"""
Endpoints for comments on reviews
"""


# Create a Comment
@router.post(
    "reviews/{review_id}/comments/", response={201: ReviewCommentOut}, auth=JWTAuth()
)
def create_comment(request, review_id: int, payload: ReviewCommentCreateSchema):
    user = request.auth
    review = Review.objects.get(id=review_id)

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    parent_comment = None

    if payload.parent_id:
        parent_comment = ReviewComment.objects.get(id=payload.parent_id)

        if parent_comment.parent and parent_comment.parent.parent:
            return 400, {"message": "Exceeded maximum comment nesting level of 3"}

    comment = ReviewComment.objects.create(
        review=review,
        community=review.community,
        author=user,
        rating=payload.rating,
        content=payload.content,
        parent=parent_comment,
    )
    # Create an anonymous name for the user who created the comment
    comment.get_anonymous_name()

    # Return comment with replies
    return 201, ReviewCommentOut.from_orm_with_replies(comment, user)


# Get a Comment
@router.get(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, 404: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    comment = ReviewComment.objects.get(id=comment_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        comment.community
        and not comment.community.is_member(current_user)
        and comment.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    return 200, ReviewCommentOut.from_orm_with_replies(comment, current_user)


@router.get(
    "reviews/{review_id}/comments/",
    response=List[ReviewCommentOut],
    auth=OptionalJWTAuth,
)
def list_review_comments(request, review_id: int):
    review = Review.objects.get(id=review_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        review.community
        and not review.community.is_member(current_user)
        and review.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    comments = (
        ReviewComment.objects.filter(review=review, parent=None)
        .select_related("author")
        .order_by("-created_at")
    )

    return [
        ReviewCommentOut.from_orm_with_replies(comment, current_user)
        for comment in comments
    ]


@router.put(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, 403: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: ReviewCommentUpdateSchema):
    comment = ReviewComment.objects.get(id=comment_id)

    if comment.author != request.auth:
        return 403, {"message": "You do not have permission to update this comment."}

    if comment.community and not comment.community.is_member(request.auth):
        return 403, {"message": "You are not a member of this community."}

    comment.content = payload.content or comment.content
    comment.rating = payload.rating or comment.rating

    comment.save()

    return 200, ReviewCommentOut.from_orm_with_replies(comment, request.auth)


@router.delete(
    "reviews/comments/{comment_id}/", response={204: None, 403: Message}, auth=JWTAuth()
)
def delete_comment(request, comment_id: int):
    user = request.auth
    comment = ReviewComment.objects.get(id=comment_id)

    # Check if the user is the owner of the comment or has permission to delete it
    if comment.author != user:
        return 403, {"message": "You do not have permission to delete this comment."}

    # Delete reactions associated with the comment
    Reaction.objects.filter(
        content_type__model="reviewcomment", object_id=comment.id
    ).delete()

    # Logically delete the comment by clearing its content and marking it as deleted
    comment.content = "[deleted]"
    comment.is_deleted = True
    comment.save()

    return 204, None
