from typing import List, Optional

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from ninja import File, Router, UploadedFile
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from articles.schemas import (
    ArticleCreateSchema,
    ArticleDetails,
    ArticleResponseSchema,
    ArticleUpdateSchema,
    CommunityDetailsForArticle,
    Message,
)
from users.auth import JWTAuth

router = Router(tags=["Articles"])


@router.post(
    "/articles/",
    response={200: ArticleResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_article(
    request,
    details: ArticleCreateSchema,
    image_file: File[UploadedFile] = None,
    pdf_file: File[UploadedFile] = None,
):
    # Process the uploaded files
    image_file = image_file if image_file else None
    pdf_file = pdf_file if pdf_file else None

    # Generate slug from title
    slug = slugify(details.payload.title)

    try:
        # Check if the slug already exists
        if Article.objects.filter(slug=slug).exists():
            return 400, {"message": "An article with this title already exists."}

        # Create the Article instance
        article = Article.objects.create(
            title=details.payload.title,
            abstract=details.payload.abstract,
            keywords=[keyword.dict() for keyword in details.payload.keywords],
            authors=[author.dict() for author in details.payload.authors],
            article_image_url=image_file,
            article_pdf_file_url=pdf_file,
            submission_type=details.payload.submission_type,
            submitter=request.auth,
            slug=slug,
        )

        return {"id": article.id, "title": article.title, "slug": article.slug}

    except ValidationError as ve:
        return 422, {"message": f"Validation error: {ve.message_dict}"}
    except Exception as e:
        return 500, {"message": f"Internal server error: {str(e)}"}


# Update Article
@router.put(
    "/{article_id}",
    response={200: ArticleResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_article(
    request,
    article_id: int,
    details: ArticleUpdateSchema,
    image_file: File[UploadedFile] = None,
    pdf_file: File[UploadedFile] = None,
):
    # Process the uploaded files
    image_file = image_file if image_file else None
    pdf_file = pdf_file if pdf_file else None

    try:
        article = Article.objects.get(id=article_id)

        # Check if the user is the submitter
        if article.submitter != request.auth:
            return 403, {"message": "You don't have permission to update this article."}

        # Update the article fields only if they are provided
        if details.payload.title:
            article.title = details.payload.title
        if details.payload.abstract:
            article.abstract = details.payload.abstract
        if details.payload.keywords:
            article.keywords = [keyword.dict() for keyword in details.payload.keywords]
        if details.payload.authors:
            article.authors = [author.dict() for author in details.payload.authors]
        if details.payload.faqs:
            article.faqs = [faq.dict() for faq in details.payload.faqs]

        # Only update the image and pdf file if a new file is uploaded
        if image_file:
            article.article_image_url = image_file
        if pdf_file:
            article.article_pdf_file_url = pdf_file

        article.submission_type = details.payload.submission_type
        article.save()

        return {"id": article.id, "title": article.title, "slug": article.slug}

    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}
    except ValidationError as ve:
        return 422, {"message": f"Validation error: {ve.message_dict}"}
    except Exception as e:
        return 500, {"message": f"Internal server error: {str(e)}"}


# Todo: Make this Endpoint partially protected
@router.get(
    "/article/{article_slug}",
    response={200: ArticleDetails, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_article(request, article_slug: str):
    try:
        article = Article.objects.get(slug=article_slug)

        # Check submission type and user's access
        if article.submission_type == "Private" and article.submitter != request.auth:
            return 403, {"message": "You don't have access to this article."}

        # If the article is submitted to a hidden community,
        # only the members can view it
        if article.community and article.community.type == "private":
            if request.auth not in article.community.members.all():
                return 403, {"message": "You don't have access to this article."}

        community = article.community

        if community:
            community_details = CommunityDetailsForArticle(
                name=community.name,
                profile_pic_url=community.profile_pic_url,
                description=community.description,
            )
        else:
            community_details = None

        article_data = ArticleDetails(
            id=article.id,
            title=article.title,
            abstract=article.abstract,
            keywords=article.keywords,
            authors=article.authors,
            article_image_url=article.article_image_url,
            article_pdf_file_url=article.article_pdf_file_url,
            submission_type=article.submission_type,
            submitter_id=article.submitter.id,
            slug=article.slug,
            community=community_details,
            status=article.status,
            published=article.published,
            created_at=article.created_at,
            updated_at=article.updated_at,
            faqs=article.faqs,
            is_submitter=article.submitter == request.auth,
        )

        return 200, article_data

    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}
    except Exception as e:
        return 500, {"message": f"Internal server error: {str(e)}"}


@router.get("/", response=List[ArticleDetails], summary="Get Public Articles")
def get_public_articles(
    request,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    rating: Optional[int] = None,
    page: int = 1,
    limit: int = 10,
):
    """
    Fetches and filters articles visible to the public based on their submission status
    and community affiliation.

    This endpoint allows for filtering and sorting of articles that:
    i) Are not submitted to any community.
    ii) Are published by communities.
    iii) Are submitted and accepted (but not published) in a public community.

    Parameters:
    - search (str, optional): Filter articles by title.
    - community (int, optional): Filter articles by community ID.
    - sort (str, optional): Sort articles ('latest', 'popular', 'older').
    - rating (int, optional): Filter articles by minimum rating.

    Returns:
    - List[ArticleSchema]: Serialized articles matching the filters.
    """

    query = (
        Q(community__isnull=True)
        | Q(published=True)
        | Q(community__type="public", status="Approved")
    )
    articles = Article.objects.filter(query)

    if search:
        articles = articles.filter(title__icontains=search)

    # Todo: Add rating field to the Article model
    # if rating:
    #     articles = articles.filter(rating__gte=rating)

    if sort:
        if sort == "latest":
            articles = articles.order_by("-id")
        # Todo: Implement sorting by popularity
        # elif sort == "popular":
        #     articles = articles.order_right(
        #         "-popularity"
        #     )
        elif sort == "older":
            articles = articles.order_by("id")

    paginator = Paginator(articles, limit)
    paginated_articles = paginator.get_page(page)

    return paginated_articles.object_list
