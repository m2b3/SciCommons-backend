from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from ninja import File, Form, Router, UploadedFile
from ninja.errors import HttpError

from articles.models import Article, Reply, Review, ReviewHistory
from articles.schemas import (
    ArticleCreateSchema,
    ArticleResponseSchema,
    ArticleReviewsResponseSchema,
    ArticleSchema,
    ReplyResponseSchema,
    ReplySchema,
    ReviewEditSchema,
    ReviewResponseSchema,
    ReviewSchema,
)
from users.auth import JWTAuth

router = Router(tags=["Articles"])


@router.post("/articles/", response=ArticleResponseSchema, auth=JWTAuth())
def create_article(
    request,
    details: Form[ArticleCreateSchema],
    image_file: File[UploadedFile] = None,
    pdf_file: File[UploadedFile] = None,
):
    # Check if the user is authenticated
    if not request.auth:
        raise HttpError(401, "You must be logged in to submit articles.")

    # Process the uploaded files
    image_file = image_file if image_file else None
    pdf_file = pdf_file if pdf_file else None

    # Generate slug from title
    slug = slugify(details.title)

    try:
        # Check if the slug already exists
        if Article.objects.filter(slug=slug).exists():
            raise HttpError(400, "An article with this title already exists.")

        # Create the Article instance
        article = Article.objects.create(
            title=details.title,
            abstract=details.abstract,
            keywords=details.keywords,
            authors=details.authors,
            image=image_file,
            pdf_file=pdf_file,
            submission_type=details.submission_type,
            submitter=request.auth,
            slug=slug,
        )

        return {"id": article.id, "title": article.title, "slug": article.slug}

    except ValidationError as ve:
        raise HttpError(422, f"Validation error: {ve.message_dict}")
    except Exception as e:
        raise HttpError(500, f"Internal server error: {str(e)}")


@router.get(
    "/articles/{article_id}",
    response={200: ArticleSchema, 404: str, 403: str, 500: str},
    auth=JWTAuth(),
)
def get_article(request, article_id: int, page: int = 1, page_size: int = 10):
    try:
        article = get_object_or_404(Article, id=article_id)

        # Check submission type and user's access
        if article.submission_type == "Private" and article.submitter != request.auth:
            return 403, "You do not have permission to view this article."

        reviews = Review.objects.filter(article=article).order_by("-created_at")
        paginator = Paginator(reviews, page_size)
        page_obj = paginator.get_page(page)

        review_data = []
        for review in page_obj:
            review_data.append(
                {
                    "id": review.id,
                    "user": review.user.id,
                    "rating": review.rating,
                    "subject": review.subject,
                    "content": review.content,
                    "created_at": review.created_at.isoformat(),
                    "updated_at": review.updated_at.isoformat(),
                }
            )

        paginated_reviews = {
            "count": paginator.count,
            "next": page_obj.next_page_number() if page_obj.has_next() else None,
            "previous": (
                page_obj.previous_page_number() if page_obj.has_previous() else None
            ),
            "results": review_data,
        }

        article_data = {
            "id": article.id,
            "title": article.title,
            "abstract": article.abstract,
            "keywords": article.keywords,
            "authors": article.authors,
            "image": article.image.url if article.image else None,
            "pdf_file": article.pdf_file.url if article.pdf_file else None,
            "submission_type": article.submission_type,
            "submitter": article.submitter.id,
            "slug": article.slug,
            "reviews": paginated_reviews,
        }

        return 200, article_data

    except HttpError as e:
        if e.status_code == 404:
            return 404, "Article not found."
        return 500, "An unexpected error occurred."

    except Exception as e:
        return 500, f"An unexpected error occurred: {str(e)}"


@router.get(
    "/articles/{article_id}/reviews/",
    response={200: ArticleReviewsResponseSchema, 404: str},
    auth=JWTAuth(),
)
def get_reviews(request, article_id: int, page: int = 1, page_size: int = 10):
    article = get_object_or_404(Article, id=article_id)

    reviews = Review.objects.filter(article=article).order_by("-created_at")
    paginator = Paginator(reviews, page_size)
    page_obj = paginator.get_page(page)

    review_data = []
    for review in page_obj:
        review_data.append(
            {
                "id": review.id,
                "user": review.user.id,
                "rating": review.rating,
                "subject": review.subject,
                "content": review.content,
                "created_at": review.created_at.isoformat(),
                "updated_at": review.updated_at.isoformat(),
            }
        )

    paginated_reviews = {
        "count": paginator.count,
        "next": page_obj.next_page_number() if page_obj.has_next() else None,
        "previous": (
            page_obj.previous_page_number() if page_obj.has_previous() else None
        ),
        "results": review_data,
    }

    return 200, paginated_reviews


@router.post(
    "/reviews/", response={201: ReviewResponseSchema, 400: str}, auth=JWTAuth()
)
def create_review(request, review: ReviewSchema):
    user = request.auth

    # Check if the article exists
    article = get_object_or_404(Article, id=review.article_id)

    # Ensure the owner of the article can't review their own article
    if article.submitter == user:
        return 400, "You can't review your own article."

    # Ensure the rating is within the accepted range
    if not (1 <= review.rating <= 5):
        return 400, "Rating must be between 1 and 5."

    try:
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
    except IntegrityError as e:
        return 400, f"Integrity error: {str(e)}"
    except ValidationError as e:
        return 400, f"Validation error: {str(e)}"
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.put(
    "/reviews/{review_id}/",
    response={200: ReviewResponseSchema, 400: str},
    auth=JWTAuth(),
)
def edit_review(request, review_id: int, review_data: ReviewEditSchema):
    user = request.auth

    # Check if the review exists and belongs to the user
    review = get_object_or_404(Review, id=review_id, user=user)

    # Ensure the rating is within the accepted range
    if not (1 <= review_data.rating <= 5):
        return 400, "Rating must be between 1 and 5."

    try:
        # Store the current state in the ReviewHistory model before updating
        ReviewHistory.objects.create(
            review=review,
            rating=review.rating,
            subject=review.subject,
            content=review.content,
        )

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
            "article_id": review.article.id,
            "user_id": review.user.id,
        }
    except IntegrityError as e:
        return 400, f"Integrity error: {str(e)}"
    except ValidationError as e:
        return 400, f"Validation error: {str(e)}"
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.post("/replies/", response={201: ReplyResponseSchema, 400: str}, auth=JWTAuth())
def create_reply(request, reply: ReplySchema):
    user = request.auth

    # Check if the review exists
    review = get_object_or_404(Review, id=reply.review_id)

    try:
        new_reply = Reply(
            review=review,
            user=user,
            content=reply.content,
        )
        new_reply.save()
        return 201, {
            "id": new_reply.id,
            "content": new_reply.content,
            "review_id": new_reply.review.id,
            "user_id": new_reply.user.id,
        }
    except IntegrityError as e:
        return 400, f"Integrity error: {str(e)}"
    except ValidationError as e:
        return 400, f"Validation error: {str(e)}"
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"
