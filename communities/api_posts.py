from typing import List, Optional

from ninja import File, Router, UploadedFile
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from articles.schemas import ArticleCreateSchema, ArticleDetails, ArticleResponseSchema
from communities.models import Community
from communities.schemas import Message
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Notification

# Initialize a router for the communities API
router = Router(tags=["Community Posts"])


# Todo: Add Pagination
@router.get(
    "/{community_id}/community_articles",
    response={200: List[ArticleDetails], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
    summary="Get articles in a community",
)
def get_community_articles(
    request,
    community_id: int,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    rating: Optional[int] = None,
):
    """
    Retrieves a list of articles associated with a specific community identified by
    its id. The endpoint filters articles based on community visibility rules:

    This endpoint supports filtering articles by search keywords, sorting
    (latest, popular, older), and minimum rating.

    Parameters:
        request (HttpRequest): The standard HttpRequest object.
        community_id (str): The id of the community for which to retrieve articles.
        search (str, optional): Keyword to filter articles based on their titles.
        Defaults to None.
        sort (str, equal to):
            - 'latest' - Orders articles by newest first.
            - 'popular' - Orders articles by popularity.
            - 'older' - Orders articles by oldest first.
        rating (int, optional): Filters articles that have a rating greater than
        or equal to the specified value.

    Returns:
        List[ArticleSchema]: A list of articles that meet the criteria, serialized
        by ArticleSchema.
        HTTP 404: If the specified community does not exist.
        HTTP 500: If there is any other error during the retrieval process.
    """

    try:
        community = Community.objects.get(id=community_id)
        user = getattr(request, "auth", None)  # Use the authenticated user if present

        if community.type == "hidden":
            if not user:
                return 403, {
                    "message": "You must be logged in to \
                    view articles in a hidden community"
                }

            # The user must be either a member or an admin of the community
            if (
                not community.members.filter(id=user.id).exists()
                and not community.admins.filter(id=user.id).exists()
                and not community.reviewers.filter(id=user.id).exists()
                and not community.moderators.filter(id=user.id).exists()
            ):
                return 403, {
                    "message": "You must be a member of the community to view articles"
                }

        articles = Article.objects.filter(community=community, status="Approved")
        if search:
            articles = articles.filter(title__icontains=search)

        # Todo: Add rating field to the Article model
        # if rating:
        #     articles = articles.filter(
        #         rating__gte=rating
        #     )

        if sort:
            if sort == "latest":
                articles = articles.order_by("-id")
            # Todo: Add more sorting options
            # elif sort == "popular":
            #     articles = articles.order_by(
            #         "-popularity"
            #     )
            elif sort == "older":
                articles = articles.order_by("id")

        return articles
    except Community.DoesNotExist:
        return 404, {"error": "Community not found"}
    except Exception as e:
        return 500, {"error": str(e)}


@router.post(
    "/{community_name}/create_community_article",
    response={201: ArticleResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
    summary="Create an article in a community",
)
def create_community_article(
    request,
    community_name: str,
    details: ArticleCreateSchema,
    image_file: File[UploadedFile] = None,
    pdf_file: File[UploadedFile] = None,
):
    try:
        # Get the community object
        community = Community.objects.get(name=community_name)

        # Check if the user is a member of the community
        if (
            not community.members.filter(id=request.auth.id).exists()
            and not community.admins.filter(id=request.auth.id).exists()
            and not community.reviewers.filter(id=request.auth.id).exists()
            and not community.moderators.filter(id=request.auth.id).exists()
        ):
            return 403, {
                "message": "You cannot submit articles \
                to this community as you are not a member."
            }

        image_file = image_file if image_file else None
        pdf_file = pdf_file if pdf_file else None

        # Create the article
        article = Article.objects.create(
            title=details.payload.title,
            abstract=details.payload.abstract,
            keywords=[keyword.dict() for keyword in details.payload.keywords],
            authors=[author.dict() for author in details.payload.authors],
            article_image_url=image_file,
            article_pdf_file_url=pdf_file,
            submission_type=details.payload.submission_type,
            submitter=request.auth,
            community=community,
            status="Pending",  # Default status as Pending
        )

        response = ArticleResponseSchema(
            id=article.id,
            title=article.title,
            slug=article.slug,
        )

        # Send a notification to the community admins
        Notification.objects.create(
            user=community.admins.first(),
            community=community,
            category="articles",
            notification_type="article_submitted",
            message=(
                f"New article submitted in {community.name}"
                f" by {request.auth.username}"
            ),
            link=f"/community/{community.name}/submissions",
            content=article.title,
        )

        return 201, response

    except Community.DoesNotExist:
        return 404, {"message": "Community not found"}

    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/submit-article/{article_slug}/{community_name}",
    # url_name="submit_article_to_community",
    response={200: ArticleResponseSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def submit_article_to_community(request, article_slug: str, community_name: str):
    try:
        # Check if the article exists and belongs to the user
        article = Article.objects.get(slug=article_slug, submitter=request.auth)

        # Check if the community exists
        community = Community.objects.get(name=community_name)

        # Check if the user is a member of the community
        if (
            not community.members.filter(id=request.auth.id).exists()
            and not community.admins.filter(id=request.auth.id).exists()
            and not community.reviewers.filter(id=request.auth.id).exists()
            and not community.moderators.filter(id=request.auth.id).exists()
        ):
            return 403, {"message": "You are not a member of this community."}

        # Check if the article is already submitted to a community
        if article.community:
            return 400, {"message": "Article is already submitted to a community."}

        # Submit the article to the community
        article.community = community
        article.status = "Pending"
        article.save()

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

        return 200, ArticleResponseSchema(
            id=article.id,
            title=article.title,
            slug=article.slug,
        )

    except Article.DoesNotExist:
        return 404, {"message": "Article not found or you are not the author."}

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}

    except Exception as e:
        return 500, {"message": str(e)}


"""
Create a new article within a specified community. This endpoint requires
authentication and is intended to be used by community members or admins
to submit new articles for approval.

Parameters:
- request: The HTTP request object that includes user authentication.
- payload (CreateCommunityArticleSchema): A schema representing the article
    to be created.
    It includes the title, abstract, keywords, authors, optional image and PDF file,
    submission type, and the community ID where the article should be associated.

Returns:
- ArticleSchema: The created article details if the operation is successful.
- HTTP 404: If the specified community does not exist.
- HTTP 500: If there is any other error during the creation process.

The article is initially set with a status of 'Pending' requiring community
admin approval.
"""
