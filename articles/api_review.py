from django.core.paginator import Paginator
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, Review, ReviewHistory
from articles.schemas import (
    CreateReviewDetails,
    Message,
    PaginatedReviewResponse,
    ReviewEditSchema,
    ReviewHistorySchema,
    ReviewResponseSchema,
    ReviewSchema,
)
from users.auth import JWTAuth

router = Router(tags=["Reviews"])


@router.get(
    "/articles/{article_id}/reviews/",
    response={
        200: PaginatedReviewResponse,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def get_reviews(request, article_id: int, page: int = 1, limit: int = 10):
    try:
        reviews = Review.objects.filter(article_id=article_id).order_by("-created_at")
        paginator = Paginator(reviews, limit)
        paginated_reviews = paginator.get_page(page)

        response_data = {
            "total": paginator.count,
            "page": page,
            "limit": limit,
            "reviews": [],
        }

        for review in paginated_reviews:
            review_history = ReviewHistory.objects.filter(review=review).order_by(
                "-edited_at"
            )
            history_data = [
                ReviewHistorySchema(
                    rating=history.rating,
                    subject=history.subject,
                    content=history.content,
                    edited_at=history.edited_at,
                )
                for history in review_history
            ]
            response_data["reviews"].append(
                ReviewSchema(
                    id=review.id,
                    article_id=review.article_id,
                    user_id=review.user_id,
                    rating=review.rating,
                    subject=review.subject,
                    content=review.content,
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                    history=history_data,
                    is_author=request.auth == review.user,
                )
            )

        return response_data
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/reviews/",
    response={201: ReviewResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_review(request, review: CreateReviewDetails):
    try:
        user = request.auth

        # Check if the article exists
        article = Article.objects.get(id=review.article_id)

        # Ensure the owner of the article can't review their own article
        if article.submitter == user:
            return 400, {"message": "You can't review your own article."}

        # Check if the user has already reviewed the article
        if Review.objects.filter(article=article, user=user).exists():
            return 400, {"message": "You have already reviewed this article."}

        # Ensure the rating is within the accepted range
        if not (1 <= review.rating <= 5):
            return 400, {"message": "Rating must be between 1 and 5."}

        new_review = Review(
            article=article,
            user=user,
            rating=review.rating,
            subject=review.subject,
            content=review.content,
        )
        new_review.save()
        return 201, {
            "id": new_review.id,
            "rating": new_review.rating,
            "subject": new_review.subject,
            "content": new_review.content,
            "created_at": new_review.created_at.isoformat(),
            "updated_at": new_review.updated_at.isoformat(),
        }
    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.put(
    "/reviews/{review_id}/",
    response={200: ReviewResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def edit_review(request, review_id: int, review_data: ReviewEditSchema):
    try:
        user = request.auth

        # Check if the review exists and belongs to the user
        review = Review.objects.get(id=review_id, user=user)

        # Ensure the rating is within the accepted range
        if not (1 <= review_data.rating <= 5):
            return 400, {"message": "Rating must be between 1 and 5."}

        # # Store the current state in the ReviewHistory model before updating
        # ReviewHistory.objects.create(
        #     review=review,
        #     rating=review.rating,
        #     subject=review.subject,
        #     content=review.content,
        # )

        # Update the review with new data
        review.rating = review_data.rating
        review.subject = review_data.subject
        review.content = review_data.content
        review.save()

        return 200, {
            "id": review.id,
            "rating": review.rating,
            "subject": review.subject,
            "content": review.content,
            "created_at": review.created_at.isoformat(),
            "updated_at": review.updated_at.isoformat(),
        }
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 400, {"message": str(e)}


# delete review
@router.delete(
    "/reviews/{review_id}/",
    response={204: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    try:
        user = request.auth
        review = Review.objects.get(id=review_id, user=user)
        review.delete()
        return 204, {"message": "Review deleted successfully."}
    except Review.DoesNotExist:
        return 404, {"message": "Review not found."}
    except Exception as e:
        return 500, {"message": str(e)}
