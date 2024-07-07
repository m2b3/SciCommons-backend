from typing import List, Optional

from django.core.paginator import Paginator
from ninja import Router
from ninja.responses import codes_4xx

from articles.models import Article, Review, ReviewComment
from articles.schemas import (
    CommentCreateSchema,
    CommentSchema,
    CommentUpdateSchema,
    CreateReviewSchema,
    DeleteResponseSchema,
    Message,
    PaginatedCommentsSchema,
    PaginatedReviewSchema,
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
    response={201: DeleteResponseSchema, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    try:
        review = Review.objects.get(id=review_id)
        user = request.auth  # Assuming user is authenticated

        if review.user != user:
            return {
                "success": False,
                "message": "You do not have permission to delete this review.",
            }

        # Delete the review
        review.delete()
        return 201, {
            "success": True,
            "message": "Review and its versions have been deleted.",
        }
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 500, {"message": str(e)}


"""
Endpoints for comments on reviews
"""


@router.post(
    "/reviews/{review_id}/comments/",
    response={201: CommentSchema, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def create_comment(request, review_id: int, payload: CommentCreateSchema):
    try:
        review = Review.objects.get(id=review_id)
        user = request.auth

        # Handle nested comments
        parent_comment = None
        if payload.parent_id:
            parent_comment = ReviewComment.objects.get(id=payload.parent_id)
            # Check the nesting level
            if parent_comment.parent and parent_comment.parent.parent:
                return 400, {"message": "Exceeded maximum comment nesting level of 3"}

        comment = ReviewComment.objects.create(
            review=review, user=user, content=payload.content, parent=parent_comment
        )
        return 201, comment
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except ReviewComment.DoesNotExist:
        return 404, {"message": "Parent comment not found."}
    except Exception as e:
        return 500, {"message": str(e)}


def build_comment_tree(comments: List[CommentSchema]) -> List[CommentSchema]:
    comment_dict = {comment.id: comment for comment in comments}
    root_comments = []
    for comment in comments:
        if comment.parent_id:
            parent = comment_dict[comment.parent_id]
            if not parent.replies:
                parent.replies = []
            if comment not in parent.replies:
                parent.replies.append(comment)
        else:
            root_comments.append(comment)
    return root_comments


@router.get(
    "/reviews/{review_id}/comments/",
    response={200: PaginatedCommentsSchema, 404: Message, 500: Message},
)
def get_comments_for_review(request, review_id: int, page: int = 1, size: int = 10):
    try:
        review = Review.objects.get(id=review_id)
        comments_query = ReviewComment.objects.filter(review=review).order_by(
            "created_at"
        )
        total_comments = comments_query.count()
        paginated_comments = comments_query[(page - 1) * size : page * size]
        comments = [CommentSchema.from_orm(comment) for comment in paginated_comments]
        nested_comments = build_comment_tree(comments)
        return {
            "total": total_comments,
            "page": page,
            "size": size,
            "comments": nested_comments,
        }

    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.put(
    "/comments/{comment_id}/",
    response={201: CommentSchema, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: CommentUpdateSchema):
    try:
        comment = ReviewComment.objects.get(id=comment_id)
        if request.auth != comment.user:
            return 403, {"message": "You do not have permission to update this comment"}

        if payload.content:
            comment.content = payload.content
        comment.save()
        return 201, comment
    except ReviewComment.DoesNotExist:
        return 404, {"message": "Comment not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.delete(
    "/comments/{comment_id}/",
    response={201: DeleteResponseSchema, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_comment(request, comment_id: int):
    try:
        comment = ReviewComment.objects.get(id=comment_id)
        if request.auth != comment.user:
            return {
                "success": False,
                "message": "You do not have permission to delete this comment.",
            }

        comment.delete()
        return 201, {"success": True, "message": "Comment deleted successfully."}

    except ReviewComment.DoesNotExist:
        return 404, {"message": "Comment not found."}

    except Exception as e:
        return 500, {"message": str(e)}
