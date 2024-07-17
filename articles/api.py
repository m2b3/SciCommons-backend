from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Q
from ninja import File, Router, UploadedFile
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, ArticlePDF
from articles.schemas import (
    ArticleCreateSchema,
    ArticleOut,
    ArticleUpdateSchema,
    Message,
    PaginatedArticlesResponse,
)
from communities.models import Community, CommunityArticle
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Hashtag, HashtagRelation, User

router = Router(tags=["Articles"])


@router.post(
    "/articles/",
    response={200: ArticleOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_article(
    request,
    details: ArticleCreateSchema,
    image_file: File[UploadedFile] = None,
    pdf_files: List[UploadedFile] = File(...),
):
    # Create the Article instance
    article = Article.objects.create(
        title=details.payload.title,
        abstract=details.payload.abstract,
        authors=[author.dict() for author in details.payload.authors],
        article_image_url=image_file,
        submission_type=details.payload.submission_type,
        submitter=request.auth,
    )

    for file in pdf_files:
        ArticlePDF.objects.create(article=article, pdf_file_url=file)
    # Todo: Create a common method to handle the creation of hashtags
    content_type = ContentType.objects.get_for_model(Article)
    for hashtag_name in details.payload.keywords:
        hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
        HashtagRelation.objects.create(
            hashtag=hashtag, content_type=content_type, object_id=article.id
        )

    if details.payload.community_id:
        community = Community.objects.get(id=details.payload.community_id)
        CommunityArticle.objects.create(article=article, community=community)
        # Todo: Send notification to the community admin

    return ArticleOut.from_orm_with_custom_fields(article, request.auth)


# Todo: Make this Endpoint partially protected
@router.get(
    "/article/{article_slug}",
    response={200: ArticleOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_article(request, article_slug: str, community_name: Optional[str] = None):
    article = Article.objects.get(slug=article_slug)

    # Check submission type and user's access
    if article.submission_type == "Private" and article.submitter != request.auth:
        return 403, {"message": "You don't have access to this article."}

    community = Community.objects.get(name=community_name) if community_name else None

    if community:
        community_article = CommunityArticle.objects.get(
            article=article, community=community
        )
        if (
            community_article.status != "Accepted"
            or community_article.status != "Published"
        ):
            return 403, {"message": "This article is not available in this community."}

        if community.type == "hidden":
            if request.auth not in community.members.all():
                return 403, {
                    "message": (
                        "You don't have access to this article in this community."
                        "Please request access from the community admin."
                    )
                }

    # Use the custom method to create the ArticleOut instance
    article_data = ArticleOut.from_orm_with_custom_fields(article, request.auth)

    return 200, article_data


# Update Article
@router.put(
    "/{article_id}",
    response={200: ArticleOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_article(
    request,
    article_id: int,
    details: ArticleUpdateSchema,
    image_file: File[UploadedFile] = None,
):
    article = Article.objects.get(id=article_id)

    # Check if the user is the submitter
    if article.submitter != request.auth:
        return 403, {"message": "You don't have permission to update this article."}

    # Update the article fields only if they are provided
    article.title = details.payload.title
    article.abstract = details.payload.abstract
    article.authors = [author.dict() for author in details.payload.authors]
    article.faqs = [faq.dict() for faq in details.payload.faqs]

    # Update Keywords
    content_type = ContentType.objects.get_for_model(Article)
    HashtagRelation.objects.filter(
        content_type=content_type, object_id=article.id
    ).delete()
    for hashtag_name in details.payload.keywords:
        hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
        HashtagRelation.objects.create(
            hashtag=hashtag, content_type=content_type, object_id=article.id
        )

    # Only update the image and pdf file if a new file is uploaded
    if image_file:
        article.article_image_url = image_file

    article.submission_type = details.payload.submission_type
    article.save()

    return ArticleOut.from_orm_with_custom_fields(article, request.auth)


@router.get(
    "/",
    response={200: PaginatedArticlesResponse, 400: Message},
    summary="Get Public Articles",
    auth=OptionalJWTAuth,
)
def get_articles(
    request,
    community_id: Optional[int] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    rating: Optional[int] = None,
    page: int = 1,
    per_page: int = 10,
):
    # Start with all public articles
    articles = Article.objects.filter(submission_type="Public").order_by("-created_at")

    current_user: Optional[User] = None if not request.auth else request.auth

    if community_id:
        community = Community.objects.get(id=community_id)
        articles = articles.filter(
            communityarticle__community=community, communityarticle__status="accepted"
        )

        # If the community is hidden and the user is not a member,
        # return an empty queryset
        if community.type == "hidden" and (
            not current_user or not community.is_member(current_user)
        ):
            return 400, {"message": "You don't have access to this community."}
    else:
        # For non-community articles or when no specific community is requested
        articles = articles.filter(
            Q(communityarticle__isnull=True)  # Not associated with any community
            | Q(
                communityarticle__status="published",
                communityarticle__community__type="hidden",
            )  # Published in hidden communities
        ).distinct()

    if search:
        articles = articles.filter(title__icontains=search)

    # Todo: Add rating field to the Article model
    # if rating:
    #     articles = articles.filter(rating__gte=rating)

    if sort:
        if sort == "latest":
            articles = articles.order_by("-created_at")
        # Todo: Implement sorting by popularity
        # elif sort == "popular":
        #     articles = articles.order_by("-popularity")
        elif sort == "older":
            articles = articles.order_by("created_at")
    else:
        articles = articles.order_by("-created_at")  # Default sort by latest

    paginator = Paginator(articles, per_page)
    paginated_articles = paginator.get_page(page)

    current_user: Optional[User] = None if not request.auth else request.auth

    return PaginatedArticlesResponse(
        items=[
            ArticleOut.from_orm_with_custom_fields(article, current_user)
            for article in paginated_articles
        ],
        total=paginator.count,
        page=page,
        per_page=per_page,
        num_pages=paginator.num_pages,
    )


# Delete Article
@router.delete(
    "/{article_id}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_article(request, article_id: int):
    article = Article.objects.get(id=article_id)

    # Check if the user is the submitter
    if article.submitter != request.auth:
        return 403, {"message": "You don't have permission to delete this article."}

    # Do not delete the article, just mark it as deleted
    article.title = f"Deleted - {article.title}"

    return {"message": "Article deleted successfully."}
