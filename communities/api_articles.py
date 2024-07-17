from typing import List, Optional

from django.core.paginator import Paginator
from django.utils import timezone
from ninja import Query, Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from articles.schemas import ArticleOut, PaginatedArticlesResponse
from communities.models import ArticleSubmissionAssessment, Community, CommunityArticle
from communities.schemas import (
    ArticleStatusSchema,
    AssessmentSubmissionSchema,
    AssessorArticleSchema,
    AssessorSchema,
    Filters,
    Message,
)
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Notification, User

# Initialize a router for the communities API
router = Router(tags=["Community Articles"])


@router.post(
    "/communities/{community_name}/submit-article/{article_slug}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def submit_article(request, community_name: str, article_slug: str):
    community = Community.objects.get(name=community_name)

    # if the community isn't public and the user isn't a member, return an error
    if community.type != "public" and request.auth not in community.members.all():
        return 400, {
            "message": "You must be a member of this community to submit articles"
        }

    article = Article.objects.get(slug=article_slug)

    CommunityArticle.objects.create(
        article=article, community=community, status="submitted"
    )

    # Send a notification to the community admins
    Notification.objects.create(
        user=community.admins.first(),
        community=community,
        category="communities",
        notification_type="article_submitted",
        message=(
            f"New article submitted in {community.name} by {request.auth.username}"
        ),
        link=f"/community/{community.name}/submissions",
        content=article.title,
    )

    return {"message": "Article submitted successfully"}


"""
Community Admin related API endpoints to manage articles
"""


@router.get(
    "/communities/{community_name}/articles/",
    response=PaginatedArticlesResponse,
    summary="List articles in a community",
    auth=OptionalJWTAuth,
)
def list_community_articles(
    request,
    community_name: str,
    filters: Filters = Query(...),
    page: int = 1,
    size: int = 10,
    sort_by: str = "submitted_at",
    sort_order: str = "desc",
):
    # Check if the community exists
    community = Community.objects.get(name=community_name)
    # Start with articles for the specific community
    queryset = Article.objects.filter(communityarticle__community=community)

    if filters.status:
        queryset = queryset.filter(communityarticle__status=filters.status)
    if filters.submitted_after:
        queryset = queryset.filter(
            communityarticle__submitted_at__gte=filters.submitted_after
        )
    if filters.submitted_before:
        queryset = queryset.filter(
            communityarticle__submitted_at__lte=filters.submitted_before
        )

    # Sorting
    if sort_by in ["submitted_at", "published_at"]:
        sort_field = f"communityarticle__{sort_by}"
    else:
        sort_field = sort_by
    sort_prefix = "-" if sort_order.lower() == "desc" else ""
    queryset = queryset.order_by(f"{sort_prefix}{sort_field}")

    queryset = queryset.distinct()

    # Pagination
    paginator = Paginator(queryset, size)
    paginated_articles = paginator.get_page(page)

    current_user: Optional[User] = None if not request.auth else request.auth

    return {
        "items": [
            ArticleOut.from_orm_with_custom_fields(article, current_user)
            for article in paginated_articles
        ],
        "total": paginator.count,
        "page": page,
        "per_page": size,
        "num_pages": paginator.num_pages,
    }


@router.post(
    "/communities/{community_id}/articles/{article_id}/approve/",
    response={200: Message, 400: Message},
    auth=JWTAuth(),
)
def approve_article(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    reviewer_count = community_article.community.reviewers.count()
    moderator_count = community_article.community.moderators.count()

    if reviewer_count == 0 and moderator_count == 0:
        community_article.status = "accepted"
        community_article.save()
        return {
            "message": "No reviewers or moderators in the community. Article approved"
        }

    assign_assessors(community_article)
    community_article.status = "under_review"
    community_article.save()
    return {"message": "Article approved and assessors assigned"}


@router.post(
    "/communities/{community_id}/articles/{article_id}/reject/",
    response={200: Message, 400: Message},
    auth=JWTAuth(),
)
def reject_article(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    community_article.status = "rejected"
    community_article.save()
    return {"message": "Article rejected successfully"}


def assign_assessors(community_article: CommunityArticle):
    community = community_article.community
    reviewers = community.reviewers.order_by("?")[:3]
    moderator = community.moderators.order_by("?").first()

    for reviewer in reviewers:
        ArticleSubmissionAssessment.objects.create(
            community_article=community_article, assessor=reviewer, is_moderator=False
        )
        # Send a notification to the reviewer
        Notification.objects.create(
            user=reviewer,
            community=community,
            category="articles",
            notification_type="article_assigned",
            message=(
                f"New article assigned to you in {community.name}"
                f" by {community_article.article.submitter.username}"
            ),
            link=f"/community/{community.name}/submissions",
            content=community_article.article.title,
        )

    if moderator:
        ArticleSubmissionAssessment.objects.create(
            community_article=community_article, assessor=moderator, is_moderator=True
        )
        # Send a notification to the moderator
        Notification.objects.create(
            user=moderator,
            community=community,
            category="articles",
            notification_type="article_assigned",
            message=(
                f"New article assigned to you in {community.name}"
                f" by {community_article.article.submitter.username}"
            ),
            link=f"/community/{community.name}/submissions",
            content=community_article.article.title,
        )


@router.get(
    "/communities/{community_id}/articles/{article_id}/status/",
    response=ArticleStatusSchema,
    auth=JWTAuth(),
)
def get_article_status(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    if request.auth not in community_article.community.members.all():
        return 400, {"message": "You are not a member of this community"}

    return {
        "status": community_article.status,
        "submitted_at": community_article.submitted_at,
        "published_at": community_article.published_at,
        "assessors": [
            AssessorSchema.from_orm_with_custom_fields(assessment)
            for assessment in community_article.assessments.all()
        ],
        "article": ArticleOut.from_orm_with_custom_fields(
            community_article.article, request.auth
        ),
    }


@router.post(
    "/communities/{community_id}/articles/{article_id}/publish/",
    response={200: Message, 400: Message},
)
def publish_article(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    if community_article.status != "accepted":
        return 400, {"message": "Only accepted articles can be published"}

    community_article.status = "published"
    community_article.published_at = timezone.now()
    community_article.save()
    return {"message": "Article published successfully"}


"""
Assessor related API endpoints to assess articles
"""


# Display list of articles that have been assigned to the user for assessment
@router.get(
    "/communities/{community_id}/assigned-articles/",
    response={200: List[ArticleOut], 400: Message},
    auth=JWTAuth(),
)
def get_assigned_articles(request, community_id: int):
    assigned_articles = ArticleSubmissionAssessment.objects.filter(
        assessor=request.auth, approved=None
    ).values_list("community_article_id", flat=True)
    community_articles = CommunityArticle.objects.filter(
        id__in=assigned_articles, community_id=community_id
    )

    return [
        ArticleOut.from_orm_with_custom_fields(community_article.article, request.auth)
        for community_article in community_articles
    ]


@router.get(
    "/communities/{community_id}/articles/{article_id}/assessment/",
    response={200: AssessorArticleSchema, 400: Message},
    auth=JWTAuth(),
)
def get_assessment_details(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    assessment = ArticleSubmissionAssessment.objects.get(
        community_article=community_article, assessor=request.auth
    )

    # Return article and the assessor details
    return {
        "article": ArticleOut.from_orm_with_custom_fields(
            community_article.article, request.auth
        ),
        "assessor": AssessorSchema.from_orm_with_custom_fields(assessment),
    }


@router.post(
    "/communities/{community_id}/articles/{article_id}/submit-assessment/",
    response={200: Message, 400: Message},
    auth=JWTAuth(),
)
def submit_assessment(
    request, community_id: int, article_id: int, payload: AssessmentSubmissionSchema
):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    assessment = ArticleSubmissionAssessment.objects.get(
        community_article=community_article, assessor=request.auth
    )

    assessment.approved = payload.approved
    assessment.comments = payload.comments
    assessment.save()

    # Check if all assessments have been approved
    if all(
        assessment.approved is True
        for assessment in ArticleSubmissionAssessment.objects.filter(
            community_article=community_article
        )
    ):
        community_article.status = "accepted"
        community_article.save()

    elif any(
        assessment.approved is False
        for assessment in ArticleSubmissionAssessment.objects.filter(
            community_article=community_article
        )
    ):
        community_article.status = "rejected"
        community_article.save()

    return {"message": "Assessment submitted successfully"}


"""
Below API endpoints aren't used in the current version of the app
"""


@router.get(
    "/communities/{community_id}/articles/{article_id}/assessors/",
    response={200: List[AssessorSchema], 400: Message},
)
def get_article_assessors(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )
    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    assessments = ArticleSubmissionAssessment.objects.filter(
        community_article=community_article
    )
    return [AssessorSchema.from_orm(assessment) for assessment in assessments]


@router.post(
    "/communities/{community_id}/articles/{article_id}/assign-assessors/",
    response={200: Message, 400: Message},
)
def manually_assign_assessors(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )

    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    assign_assessors(community_article)
    community_article.status = "under_review"
    community_article.save()
    return {"message": "Assessors assigned successfully"}


@router.post(
    "/communities/{community_id}/articles/{article_id}/check-assessments/",
    response={200: Message, 400: Message},
)
def check_assessments(request, community_id: int, article_id: int):
    community_article = CommunityArticle.objects.get(
        id=article_id, community_id=community_id
    )

    if request.auth not in community_article.community.admins.all():
        return 400, {"message": "You are not an admin of this community"}

    # assessments is a related manager, so we need to call all() to get the queryset
    assessments = community_article.assessments.all()

    if assessments.count() == 0:
        community_article.status = "accepted"
    elif all(
        assessment.approved
        for assessment in assessments
        if assessment.approved is not None
    ):
        community_article.status = "accepted"
    elif any(not assessment.approved for assessment in assessments):
        community_article.status = "rejected"
    else:
        return {"message": "Assessment process still ongoing"}

    community_article.save()
    return {"message": "Assessment process completed"}
