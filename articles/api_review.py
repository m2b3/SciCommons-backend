from typing import List, Optional

from django.core.paginator import Paginator
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
    ReviewResponseSchema,
    ReviewSchema,
    ReviewUpdateSchema,
)
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Reviews"])


@router.post(
    "/{article_id}/reviews/",
    response={201: ReviewResponseSchema, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def create_review(request, article_id: int, review_data: CreateReviewSchema):
    try:
        article = Article.objects.get(id=article_id)
        user = request.auth

        # Ensure the owner of the article can't review their own article
        if article.submitter == user:
            return 400, {"message": "You can't review your own article."}

        # Check if the user has already reviewed the article
        if Review.objects.filter(article=article, user=user).exists():
            return 400, {"message": "You have already reviewed this article."}

        review = Review.objects.create(
            article=article,
            user=user,
            rating=review_data.rating,
            subject=review_data.subject,
            content=review_data.content,
        )
        return 201, review
    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/{article_id}/reviews/",
    response={200: PaginatedReviewSchema, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def list_reviews(request, article_id: int, page: int = 1, size: int = 10):
    reviews = Review.objects.filter(article_id=article_id).order_by("-created_at")
    paginator = Paginator(reviews, size)
    page_obj = paginator.page(page)
    current_user: Optional[User] = None if not request.auth else request.auth

    items = [
        ReviewSchema.from_orm(review, current_user) for review in page_obj.object_list
    ]

    return PaginatedReviewSchema(
        items=items, total=paginator.count, page=page, size=size
    )


@router.put(
    "/reviews/{review_id}/",
    response={201: ReviewResponseSchema, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def update_review(request, review_id: int, review_data: ReviewUpdateSchema):
    try:
        review = Review.objects.get(id=review_id)
        user = request.auth

        # Check if the review belongs to the user
        if review.user != user:
            return 403, {"message": "You do not have permission to update this review."}

        # Update the review with new data
        review.rating = review_data.rating
        review.subject = review_data.subject
        review.content = review_data.content
        review.save()

        return 201, review
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.delete(
    "/reviews/{review_id}/",
    response={201: Message, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    try:
        review = Review.objects.get(id=review_id)
        user = request.auth  # Assuming user is authenticated

        if review.user != user:
            return 403, {"message": "You do not have permission to delete this review."}

        # Delete the review
        review.delete()
        return 201, {"message": "Review deleted successfully."}
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 500, {"message": str(e)}


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
    parent_comment = None

    if payload.parent_id:
        parent_comment = ReviewComment.objects.get(id=payload.parent_id)

        if parent_comment.parent and parent_comment.parent.parent:
            return 400, {"message": "Exceeded maximum comment nesting level of 3"}

    comment = ReviewComment.objects.create(
        review=review,
        author=user,
        content=payload.content,
        parent=parent_comment,
    )
    # Return comment with replies
    return 201, ReviewCommentOut.from_orm_with_replies(comment, user)


@router.get(
    "reviews/{review_id}/comments/",
    response=List[ReviewCommentOut],
    auth=OptionalJWTAuth,
)
def list_review_comments(request, review_id: int):
    review = Review.objects.get(id=review_id)
    comments = (
        ReviewComment.objects.filter(review=review, parent=None)
        .select_related("author")
        .order_by("-created_at")
    )
    current_user: Optional[User] = None if not request.auth else request.auth
    return [
        ReviewCommentOut.from_orm_with_replies(comment, current_user)
        for comment in comments
    ]


@router.put(
    "reviews/comments/{comment_id}/",
    response={200: Message, 403: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: ReviewCommentUpdateSchema):
    comment = ReviewComment.objects.get(id=comment_id)

    if comment.author != request.auth:
        return 403, {"message": "You do not have permission to update this comment."}

    if payload.content is not None:
        comment.content = payload.content

    comment.save()

    return 200, {"message": "Comment updated successfully"}


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
