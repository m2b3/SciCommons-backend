from datetime import timedelta
from typing import List, Optional
from urllib.parse import unquote

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from ninja import File, Query, Router, UploadedFile
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, ArticlePDF, Discussion, Reaction, Review
from articles.schemas import (
    ArticleBasicOut,
    ArticleCreateSchema,
    ArticleFilters,
    ArticleOut,
    ArticleUpdateSchema,
    CommunityArticleStatsResponse,
    DateCount,
    Message,
    OfficialArticleStatsResponse,
    PaginatedArticlesResponse,
    ReviewExcerpt,
)
from communities.models import Community, CommunityArticle
from myapp.schemas import FilterType
from myapp.utils import validate_tags
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Hashtag, HashtagRelation, Notification, User

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
    pdf_files: List[UploadedFile] = File(None),
):
    with transaction.atomic():
        user = request.auth
        # validate_tags(details.payload.keywords)
        article_title = details.payload.title.strip()
        article_abstract = details.payload.abstract.strip()
        community = None
        # If either title, abstract aren't unique, return an error
        if Article.objects.filter(
            title=article_title, abstract=article_abstract
        ).exists():
            return 400, {"message": "This article has already been submitted."}
    
        if pdf_files and len(pdf_files) > 1:
            return 400, {"message": "Only one PDF file is allowed."}

        # Check if the article link is unique
        if details.payload.article_link:
            if Article.objects.filter(
                article_link=details.payload.article_link
            ).exists():
                return 400, {"message": "This article has already been submitted."}

        # Create the Article instance
        article = Article.objects.create(
            title=article_title,
            abstract=article_abstract,
            authors=[author.dict() for author in details.payload.authors],
            article_image_url=image_file,
            article_link=details.payload.article_link or None,
            submission_type=details.payload.submission_type,
            submitter=request.auth,
        )

        # Todo: Create a common method to handle the creation of hashtags
        # content_type = ContentType.objects.get_for_model(Article)
        # for hashtag_name in details.payload.keywords:
        #     hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
        #     HashtagRelation.objects.create(
        #         hashtag=hashtag, content_type=content_type, object_id=article.id
        #     )

        if details.payload.community_name:
            community_name = unquote(details.payload.community_name)
            community = Community.objects.get(name=community_name)
            community_article_status = (
                CommunityArticle.PUBLISHED
                if community.type in {"private", "hidden"} or community.admins.filter(id=user.id).exists()
                else CommunityArticle.SUBMITTED
            )
            CommunityArticle.objects.create(article=article, community=community, status=community_article_status)

            # Send notification to the community admin
            Notification.objects.create(
                user=community.admins.first(),
                community=community,
                category="communities",
                notification_type="article_submitted",
                message=(
                    f"New article submitted in {community.name}"
                    f" by {request.auth.username}"
                ),
                link=f"/community/{community.name}/submissions",
                content=article.title,
            )
        
        if pdf_files:
            for file in pdf_files:
                ArticlePDF.objects.create(article=article, pdf_file_url=file)

        pdf_link = details.payload.pdf_link
        if pdf_link:
            ArticlePDF.objects.create(
                article=article, 
                pdf_file_url=None,
                external_url=pdf_link
            )

        return ArticleOut.from_orm_with_custom_fields(article, community, request.auth)


# Todo: Make this Endpoint partially protected
@router.get(
    "/article/{article_slug}",
    response={200: ArticleOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_article(request, article_slug: str, community_name: Optional[str] = None):
    article = Article.objects.get(slug=article_slug)
    
    community = None
    community_article = None 

    if community_name:
        community_name = unquote(community_name)
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}

    if community:
        try:
            community_article = CommunityArticle.objects.get(article=article, community=community)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Community article not found."}

        if community.type in ["hidden", "private"]:
            if request.auth not in community.members.all():
                return 403, {
                    "message": (
                        "You don't have access to this article in this community."
                        " Please request access from the community admin."
                    )
                }
    else:
        # Check submission type and user's access
        if article.submission_type == "Private" and article.submitter != request.auth:
            return 403, {"message": "You don't have access to this article."}

    if community_article and community_article.status == "rejected":
        return 403, {"message": "This article is not available in this community."}

    # Use the custom method to create the ArticleOut instance
    article_data = ArticleOut.from_orm_with_custom_fields(article, community, request.auth)

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
    with transaction.atomic():
        article = Article.objects.get(id=article_id)
        article_community = CommunityArticle.objects.filter(article=article).first() or None

        # Check if the user is the submitter
        if article.submitter != request.auth:
            return 403, {"message": "You don't have permission to update this article."}

        # Update the article fields only if they are provided
        article.title = details.payload.title
        article.abstract = details.payload.abstract
        article.authors = [author.dict() for author in details.payload.authors]
        article.faqs = [faq.dict() for faq in details.payload.faqs]

        # validate_tags(details.payload.keywords)

        # Update Keywords
        # content_type = ContentType.objects.get_for_model(Article)
        # HashtagRelation.objects.filter(
        #     content_type=content_type, object_id=article.id
        # ).delete()
        # for hashtag_name in details.payload.keywords:
        #     hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
        #     HashtagRelation.objects.create(
        #         hashtag=hashtag, content_type=content_type, object_id=article.id
        #     )

        # Only update the image and pdf file if a new file is uploaded
        if image_file:
            article.article_image_url = image_file

        article.submission_type = details.payload.submission_type
        article.save()

        return ArticleOut.from_orm_with_custom_fields(article, article_community, request.auth)


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
    articles = Article.objects.filter(submission_type="Public").order_by("-created_at") if not community_id else Article.objects.order_by("-created_at")
    community = None
    current_user: Optional[User] = None if not request.auth else request.auth

    if community_id:
        community = Community.objects.get(id=community_id)

        # If the community is hidden and the user is not a member,
        # return an empty queryset
        if community.type == "hidden" and (
            not current_user or not community.is_member(current_user)
        ):
            return 400, {"message": "You don't have access to this community."}

        # articles = Article.objects.order_by("-created_at")
        # Only display articles that are published or accepted in the community
        articles = articles.filter(
            Q(
                communityarticle__community=community,
                communityarticle__status="published",
            )
            | Q(
                communityarticle__community=community,
                communityarticle__status="accepted",
            )
        ).distinct()

    else:
        # Just do not display articles that belong to hidden communities
        articles = articles.exclude(
            communityarticle__community__type="hidden",
        )

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
            ArticleOut.from_orm_with_custom_fields(article, community, current_user)
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


"""
Article Stats Endpoints
"""


@router.get(
    "/article/{article_slug}/official-stats",
    response={200: OfficialArticleStatsResponse, 400: Message},
    auth=JWTAuth(),
)
def get_article_official_stats(request, article_slug: str):
    article = Article.objects.get(slug=article_slug)

    # Get discussions count
    discussions_count = Discussion.objects.filter(article=article).count()

    # Get likes count
    likes_count = Reaction.objects.filter(
        content_type__model="article", object_id=article.id, vote=Reaction.LIKE
    ).count()

    # Get reviews count
    reviews_count = Review.objects.filter(article=article).count()

    # Get recent reviews
    recent_reviews = Review.objects.filter(article=article).order_by("-created_at")[:3]

    # Get reviews and likes over time (last 7 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6)
    date_range = [start_date + timedelta(days=i) for i in range(7)]

    # Reviews over time
    reviews_over_time = (
        Review.objects.filter(
            article=article, created_at__date__range=[start_date, end_date]
        )
        .values("created_at__date")
        .annotate(count=Count("id"))
    )

    reviews_dict = {
        item["created_at__date"]: item["count"] for item in reviews_over_time
    }

    reviews_over_time = [
        DateCount(
            date=date,
            count=sum(reviews_dict.get(d, 0) for d in date_range if d <= date),
        )
        for date in date_range
    ]

    # Likes over time
    likes_over_time = (
        Reaction.objects.filter(
            content_type__model="article",
            object_id=article.id,
            vote=Reaction.LIKE,
            created_at__date__range=[start_date, end_date],
        )
        .values("created_at__date")
        .annotate(count=Count("id"))
    )

    likes_dict = {item["created_at__date"]: item["count"] for item in likes_over_time}

    likes_over_time = [
        DateCount(
            date=date, count=sum(likes_dict.get(d, 0) for d in date_range if d <= date)
        )
        for date in date_range
    ]

    # Get average rating
    average_rating = Review.objects.filter(article=article).aggregate(Avg("rating"))[
        "rating__avg"
    ]

    return OfficialArticleStatsResponse(
        title=article.title,
        submission_date=article.created_at.date(),
        submitter=article.submitter.username,
        discussions=discussions_count,
        likes=likes_count,
        reviews_count=reviews_count,
        recent_reviews=[
            ReviewExcerpt(excerpt=review.content[:100], date=review.created_at.date())
            for review in recent_reviews
        ],
        reviews_over_time=reviews_over_time,
        likes_over_time=likes_over_time,
        average_rating=average_rating or 0,
    )


@router.get(
    "/article/{article_slug}/community-stats",
    response={200: CommunityArticleStatsResponse, 400: Message},
    auth=JWTAuth(),
)
def get_community_article_stats(request, article_slug: str):
    article = Article.objects.get(slug=article_slug)

    try:
        community_article = CommunityArticle.objects.get(article=article)
        community = community_article.community
        submission_date = community_article.submitted_at
        community_name = community.name  # Assuming Community model has a 'name' field
    except CommunityArticle.DoesNotExist:
        community = None
        submission_date = article.created_at
        community_name = None

    # Get discussions count
    discussions_count = Discussion.objects.filter(
        article=article, community=community
    ).count()

    # Get likes count
    likes_count = Reaction.objects.filter(
        content_type__model="article", object_id=article.id, vote=Reaction.LIKE
    ).count()

    # Get reviews count and data
    reviews = Review.objects.filter(article=article, community=community)
    reviews_count = reviews.count()

    # Get recent reviews
    recent_reviews = reviews.order_by("-created_at")[:3]

    # Get reviews and likes over time (last 7 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6)
    date_range = [start_date + timedelta(days=i) for i in range(7)]

    # Reviews over time
    reviews_over_time = (
        reviews.filter(created_at__date__range=[start_date, end_date])
        .values("created_at__date")
        .annotate(count=Count("id"))
    )

    reviews_dict = {
        item["created_at__date"]: item["count"] for item in reviews_over_time
    }

    reviews_over_time = [
        DateCount(
            date=date,
            count=sum(reviews_dict.get(d, 0) for d in date_range if d <= date),
        )
        for date in date_range
    ]

    # Likes over time
    likes_over_time = (
        Reaction.objects.filter(
            content_type__model="article",
            object_id=article.id,
            vote=Reaction.LIKE,
            created_at__date__range=[start_date, end_date],
        )
        .values("created_at__date")
        .annotate(count=Count("id"))
    )

    likes_dict = {item["created_at__date"]: item["count"] for item in likes_over_time}

    likes_over_time = [
        DateCount(
            date=date, count=sum(likes_dict.get(d, 0) for d in date_range if d <= date)
        )
        for date in date_range
    ]

    # Get average rating
    average_rating = round(reviews.aggregate(Avg("rating"))["rating__avg"] or 0, 1)

    return CommunityArticleStatsResponse(
        title=article.title,
        submission_date=submission_date.date(),
        submitter=article.submitter.username,
        community_name=community_name,
        discussions=discussions_count,
        likes=likes_count,
        reviews_count=reviews_count,
        recent_reviews=[
            ReviewExcerpt(excerpt=review.content[:100], date=review.created_at.date())
            for review in recent_reviews
        ],
        reviews_over_time=reviews_over_time,
        likes_over_time=likes_over_time,
        average_rating=average_rating or 0,
    )


"""
Relevant Articles Endpoint
"""


@router.get(
    "/{article_id}/relevant-articles",
    response=List[ArticleBasicOut],
    auth=OptionalJWTAuth,
)
def get_relevant_articles(
    request, article_id: int, filters: ArticleFilters = Query(...)
):
    base_article = Article.objects.get(id=article_id)

    # Get hashtags of the base article
    base_hashtags = base_article.hashtags.values_list("hashtag_id", flat=True)

    # Query for relevant articles
    queryset = Article.objects.exclude(id=article_id).exclude(
        communityarticle__community__type="hidden"
    )

    # Calculate relevance score based on shared hashtags
    queryset = queryset.annotate(
        relevance_score=Count(
            "hashtags", filter=Q(hashtags__hashtag_id__in=base_hashtags)
        )
    ).filter(relevance_score__gt=0)

    if filters.community_id:
        queryset = queryset.filter(
            communityarticle__community_id=filters.community_id,
            communityarticle__community__type__ne="hidden",
        )

    if filters.filter_type == FilterType.POPULAR:
        queryset = queryset.annotate(
            popularity_score=Count("reviews") + Count("discussions")
        ).order_by("-popularity_score", "-relevance_score")
    elif filters.filter_type == FilterType.RECENT:
        queryset = queryset.order_by("-created_at", "-relevance_score")
    else:  # "relevant" is the default
        queryset = queryset.order_by("-relevance_score", "-created_at")

    articles = queryset[filters.offset : filters.offset + filters.limit]

    return [
        ArticleBasicOut.from_orm_with_custom_fields(article, request.auth)
        for article in articles
    ]
