from datetime import timedelta
from typing import List, Optional
from urllib.parse import quote_plus, unquote

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
    try:
        with transaction.atomic():
            user = request.auth
            # validate_tags(details.payload.keywords)
            article_title = details.payload.title.strip()
            article_abstract = details.payload.abstract.strip()
            community = None
            
            # If either title, abstract aren't unique, return an error
            try:
                if Article.objects.filter(
                    title=article_title, abstract=article_abstract
                ).exists():
                    return 400, {"message": "This article has already been submitted."}
            except Exception:
                return 500, {"message": "Error checking article uniqueness. Please try again."}
        
            if pdf_files and len(pdf_files) > 1:
                return 400, {"message": "Only one PDF file is allowed."}

            # Check if the article link is unique
            try:
                if details.payload.article_link:
                    if Article.objects.filter(
                        article_link=details.payload.article_link
                    ).exists():
                        return 400, {"message": "This article has already been submitted."}
            except Exception:
                return 500, {"message": "Error checking article link uniqueness. Please try again."}

            # Create the Article instance
            try:
                article = Article.objects.create(
                    title=article_title,
                    abstract=article_abstract,
                    authors=[author.dict() for author in details.payload.authors],
                    article_image_url=image_file,
                    article_link=details.payload.article_link or None,
                    submission_type=details.payload.submission_type,
                    submitter=request.auth,
                )
            except Exception:
                return 500, {"message": "Error creating article. Please try again."}

            # Todo: Create a common method to handle the creation of hashtags
            # content_type = ContentType.objects.get_for_model(Article)
            # for hashtag_name in details.payload.keywords:
            #     hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
            #     HashtagRelation.objects.create(
            #         hashtag=hashtag, content_type=content_type, object_id=article.id
            #     )

            if details.payload.community_name:
                try:
                    community_name = unquote(details.payload.community_name)
                    community = Community.objects.get(name=community_name)
                    community_article_status = (
                        CommunityArticle.PUBLISHED
                        if community.type in {"private", "hidden"} or community.admins.filter(id=user.id).exists()
                        else CommunityArticle.SUBMITTED
                    )
                    CommunityArticle.objects.create(article=article, community=community, status=community_article_status)

                    # Send notification to the community admin
                    try:
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
                    except Exception:
                        # Continue even if notification creation fails
                        pass
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}
                except Exception:
                    return 500, {"message": "Error associating article with community. Please try again."}
            
            try:
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
            except Exception:
                return 500, {"message": "Error uploading PDF files. Please try again."}
                
            try:
                response_data = ArticleOut.from_orm_with_custom_fields(article, community, request.auth)
                return 200, response_data
            except Exception:
                return 500, {"message": "Article created but error retrieving article data. Please refresh to see your article."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Todo: Make this Endpoint partially protected
@router.get(
    "/article/{article_slug}",
    response={200: ArticleOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_article(request, article_slug: str, community_name: Optional[str] = None):
    try:
        try:
            article = Article.objects.get(slug=article_slug)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}
        
        community = None
        community_article = None 

        if community_name:
            try:
                community_name = unquote(community_name)
                try:
                    community = Community.objects.get(name=community_name)
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}
            except Exception as e:
                return 500, {"message": "Error processing community information. Please try again."}

        if community:
            try:
                try:
                    community_article = CommunityArticle.objects.get(article=article, community=community)
                except CommunityArticle.DoesNotExist:
                    return 404, {"message": "Article not found in this community."}
                
                # Check permissions for hidden/private communities
                try:
                    if community.type in ["hidden", "private"]:
                        if request.auth not in community.members.all():
                            return 403, {
                                "message": (
                                    "You don't have access to this article in this community."
                                    " Please request access from the community admin."
                                )
                            }
                except Exception:
                    return 500, {"message": "Error checking access permissions. Please try again."}
            except Exception:
                return 500, {"message": "Error retrieving community article. Please try again."}
        else:
            # Check submission type and user's access for non-community articles
            try:
                if article.submission_type == "Private" and article.submitter != request.auth:
                    return 403, {"message": "You don't have access to this article."}
            except Exception:
                return 500, {"message": "Error checking article permissions. Please try again."}

        if community_article and community_article.status == "rejected":
            return 403, {"message": "This article is not available in this community."}

        # Use the custom method to create the ArticleOut instance
        try:
            article_data = ArticleOut.from_orm_with_custom_fields(article, community, request.auth)
            return 200, article_data
        except Exception:
            return 500, {"message": "Error preparing article data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


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
    try:
        with transaction.atomic():
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return 404, {"message": "Article not found."}
            except Exception:
                return 500, {"message": "Error retrieving article. Please try again."}
                
            try:
                article_community = CommunityArticle.objects.filter(article=article).first()
            except Exception:
                return 500, {"message": "Error retrieving article community information. Please try again."}

            # Check if the user is the submitter
            if article.submitter != request.auth:
                return 403, {"message": "You don't have permission to update this article."}

            try:
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
            except Exception:
                return 500, {"message": "Error updating article. Please try again."}

            try:
                # Extract the community from article_community if it exists
                community = article_community.community if article_community else None
                response_data = ArticleOut.from_orm_with_custom_fields(article, community, request.auth)
                return 200, response_data
            except Exception:
                return 500, {"message": "Article updated but error retrieving article data. Please refresh to see your changes."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/",
    response={200: PaginatedArticlesResponse, codes_4xx: Message, codes_5xx: Message},
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
    try:
        # Start with all public articles
        try:
            articles = Article.objects.filter(submission_type="Public").order_by("-created_at") if not community_id else Article.objects.order_by("-created_at")
        except Exception:
            return 500, {"message": "Error retrieving articles. Please try again."}
            
        community = None
        current_user: Optional[User] = None if not request.auth else request.auth

        if community_id:
            try:
                try:
                    community = Community.objects.get(id=community_id)
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}

                # If the community is hidden and the user is not a member,
                # return an empty queryset
                if community.type == "hidden" and (
                    not current_user or not community.is_member(current_user)
                ):
                    return 403, {"message": "You don't have access to this community."}

                # Only display articles that are published or accepted in the community
                try:
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
                except Exception:
                    return 500, {"message": "Error filtering community articles. Please try again."}
            except Exception:
                return 500, {"message": "Error processing community information. Please try again."}
        else:
            # Just do not display articles that belong to hidden communities
            try:
                articles = articles.exclude(
                    communityarticle__community__type="hidden",
                )
            except Exception:
                return 500, {"message": "Error filtering articles. Please try again."}

        try:
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
            else:
                articles = articles.order_by("-created_at")  # Default sort by latest
        except Exception:
            return 500, {"message": "Error sorting or filtering articles. Please try again."}

        try:
            paginator = Paginator(articles, per_page)
            paginated_articles = paginator.get_page(page)
        except Exception:
            return 400, {"message": "Error with pagination parameters. Please try different values."}

        try:
            response_data = PaginatedArticlesResponse(
                items=[
                    ArticleOut.from_orm_with_custom_fields(article, community, current_user)
                    for article in paginated_articles
                ],
                total=paginator.count,
                page=page,
                per_page=per_page,
                num_pages=paginator.num_pages,
            )

            return 200, response_data
        except Exception:
            return 500, {"message": "Error preparing article data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Delete Article
@router.delete(
    "/{article_id}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_article(request, article_id: int):
    try:
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        # Check if the user is the submitter
        if article.submitter != request.auth:
            return 403, {"message": "You don't have permission to delete this article."}

        try:
            # Do not delete the article, just mark it as deleted
            article.title = f"Deleted - {article.title}"
            article.save()
        except Exception:
            return 500, {"message": "Error deleting article. Please try again."}

        return {"message": "Article deleted successfully."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Article Stats Endpoints
"""


@router.get(
    "/article/{article_slug}/official-stats",
    response={200: OfficialArticleStatsResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_article_official_stats(request, article_slug: str):
    try:
        try:
            article = Article.objects.get(slug=article_slug)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
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

            response_data = OfficialArticleStatsResponse(
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

            return 200, response_data
        except Exception:
            return 500, {"message": "Error retrieving article statistics. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/article/{article_slug}/community-stats",
    response={200: CommunityArticleStatsResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_community_article_stats(request, article_slug: str):
    try:
        try:
            article = Article.objects.get(slug=article_slug)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        community = None
        community_name = None
        submission_date = None

        try:
            try:
                community_article = CommunityArticle.objects.get(article=article)
                community = community_article.community
                submission_date = community_article.submitted_at
                community_name = community.name
            except CommunityArticle.DoesNotExist:
                # Not a community article, use article's creation date
                submission_date = article.created_at
        except Exception:
            return 500, {"message": "Error retrieving community information. Please try again."}

        try:
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

            response_data = CommunityArticleStatsResponse(
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

            return 200, response_data
        except Exception:
            return 500, {"message": "Error retrieving community article statistics. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Relevant Articles Endpoint
"""


@router.get(
    "/{article_id}/relevant-articles",
    response={200: List[ArticleBasicOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_relevant_articles(
    request, article_id: int, filters: ArticleFilters = Query(...)
):
    try:
        try:
            base_article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            # Get hashtags of the base article
            base_hashtags = base_article.hashtags.values_list("hashtag_id", flat=True)

            # Query for relevant articles
            queryset = Article.objects.exclude(id=article_id).exclude(
                communityarticle__community__type="hidden"
            )

            # Calculate relevance score based on shared hashtagsY
            queryset = queryset.annotate(
                relevance_score=Count(
                    "hashtags", filter=Q(hashtags__hashtag_id__in=base_hashtags)
                )
            ).filter(relevance_score__gt=0)

            if filters.community_id:
                try:
                    queryset = queryset.filter(
                        communityarticle__community_id=filters.community_id,
                        communityarticle__community__type__ne="hidden",
                    )
                except Exception:
                    return 500, {"message": "Error filtering by community. Please try again."}

            if filters.filter_type == FilterType.POPULAR:
                queryset = queryset.annotate(
                    popularity_score=Count("reviews") + Count("discussions")
                ).order_by("-popularity_score", "-relevance_score")
            elif filters.filter_type == FilterType.RECENT:
                queryset = queryset.order_by("-created_at", "-relevance_score")
            else:  # "relevant" is the default
                queryset = queryset.order_by("-relevance_score", "-created_at")

            try:
                articles = queryset[filters.offset : filters.offset + filters.limit]
            except Exception:
                return 400, {"message": "Invalid pagination parameters."}

            try:
                result = [
                    ArticleBasicOut.from_orm_with_custom_fields(article, request.auth)
                    for article in articles
                ]
                return 200, result
            except Exception:
                return 500, {"message": "Error formatting article data. Please try again."}
        except Exception:
            return 500, {"message": "Error retrieving relevant articles. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}

