from typing import List, Literal, Optional

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef
from ninja import Query, Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, Review
from articles.schemas import ArticleOut, PaginatedArticlesResponse
from communities.models import Community, CommunityArticle
from communities.schemas import (
    CommunityArticlePseudonymousOut,
    Filters,
    Message,
    StatusFilter,
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
    try:
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}
            
        user = request.auth

        # if the community isn't public and the user isn't a member, return an error
        if community.type != "public" and request.auth not in community.members.all():
            return 400, {
                "message": "You must be a member of this community to submit articles"
            }

        try:
            article = Article.objects.get(slug=article_slug)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            # Check if the article is already submitted to the community
            if CommunityArticle.objects.filter(article=article, community=community).exists():
                return 400, {"message": "This article is already submitted to this community."}
        except Exception:
            return 500, {"message": "Error checking article submission status. Please try again."}
        
        try:
            community_article_status = (
                CommunityArticle.PUBLISHED
                if community.type in {"private", "hidden"} or community.admins.filter(id=user.id).exists()
                else CommunityArticle.SUBMITTED
            )

            CommunityArticle.objects.create(
                article=article, community=community, status=community_article_status
            )
        except Exception:
            return 500, {"message": "Error submitting article to community. Please try again."}

        # Send a notification to the community admins
        try:
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
        except Exception:
            # Continue even if notification fails
            pass

        return 200, {"message": "Article submitted successfully"}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/articles/my-articles/",
    response={200: PaginatedArticlesResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_my_articles(
    request,
    status_filter: Optional[StatusFilter] = Query(None),
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0, le=100),
):
    try:
        user = request.auth
        try:
            articles = Article.objects.filter(submitter=user).order_by("-created_at")
        except Exception:
            return 500, {"message": "Error retrieving your articles. Please try again."}

        try:
            if status_filter:
                if status_filter == StatusFilter.PUBLISHED:
                    # Filter articles that are published in any community
                    articles = articles.filter(
                        Exists(
                            CommunityArticle.objects.filter(
                                article=OuterRef("pk"), status=CommunityArticle.PUBLISHED
                            )
                        )
                    )
                elif status_filter == StatusFilter.UNSUBMITTED:
                    # Filter articles that are not submitted to any community
                    articles = articles.filter(
                        ~Exists(CommunityArticle.objects.filter(article=OuterRef("pk")))
                    )
                elif status_filter == StatusFilter.UNDER_REVIEW:
                    # Filter articles that are under review in any community
                    articles = articles.filter(
                        Exists(
                            CommunityArticle.objects.filter(
                                article=OuterRef("pk"), status=CommunityArticle.UNDER_REVIEW
                            )
                        )
                    )
                elif status_filter == StatusFilter.ACCEPTED:
                    # Filter articles that are accepted in any community
                    articles = articles.filter(
                        Exists(
                            CommunityArticle.objects.filter(
                                article=OuterRef("pk"), status=CommunityArticle.ACCEPTED
                            )
                        )
                    )
                elif status_filter == StatusFilter.REJECTED:
                    # Filter articles that are rejected in any community
                    articles = articles.filter(
                        Exists(
                            CommunityArticle.objects.filter(
                                article=OuterRef("pk"), status=CommunityArticle.REJECTED
                            )
                        )
                    )
        except Exception:
            return 500, {"message": "Error filtering articles. Please try again."}

        try:
            paginator = Paginator(articles, limit)
            paginated_articles = paginator.get_page(page)
        except Exception:
            return 400, {"message": "Invalid pagination parameters. Please check page number and size."}

        try:
            return 200, PaginatedArticlesResponse(
                items=[
                    ArticleOut.from_orm_with_custom_fields(article, None, user)
                    for article in paginated_articles
                ],
                total=paginator.count,
                page=page,
                per_page=limit,
                num_pages=paginator.num_pages,
            )
        except Exception:
            return 500, {"message": "Error formatting article data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Community Admin related API endpoints to manage articles
"""


@router.get(
    "/communities/{community_name}/articles/",
    response={200: PaginatedArticlesResponse, codes_4xx: Message, codes_5xx: Message},
    summary="List articles in a community",
    auth=OptionalJWTAuth,
)
def list_community_articles_by_status(
    request,
    community_name: str,
    filters: Filters = Query(...),
    page: int = 1,
    size: int = 10,
    sort_by: str = "submitted_at",
    sort_order: str = "desc",
):
    try:
        # Check if the community exists
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}
            
        try:
            # Start with articles for the specific community
            queryset = Article.objects.filter(communityarticle__community=community)

            # Apply filters
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
        except Exception:
            return 500, {"message": "Error filtering articles. Please try again."}

        try:
            # Sorting
            if sort_by in ["submitted_at", "published_at"]:
                sort_field = f"communityarticle__{sort_by}"
            else:
                sort_field = sort_by
            sort_prefix = "-" if sort_order.lower() == "desc" else ""
            queryset = queryset.order_by(f"{sort_prefix}{sort_field}")

            queryset = queryset.distinct()
        except Exception:
            return 500, {"message": "Error sorting articles. Please try again."}

        try:
            # Pagination
            paginator = Paginator(queryset, size)
            paginated_articles = paginator.get_page(page)
        except Exception:
            return 400, {"message": "Invalid pagination parameters. Please check page number and size."}

        current_user: Optional[User] = None if not request.auth else request.auth

        try:
            return 200, {
                "items": [
                    ArticleOut.from_orm_with_custom_fields(article, community, current_user)
                    for article in paginated_articles
                ],
                "total": paginator.count,
                "page": page,
                "per_page": size,
                "num_pages": paginator.num_pages,
            }
        except Exception:
            return 500, {"message": "Error formatting article data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/{community_article_id}/manage/{action}/",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def manage_article(
    request,
    community_article_id: int,
    action: Literal["approve", "reject", "publish"],
):
    try:
        user = request.auth
        
        try:
            community_article = CommunityArticle.objects.get(id=community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception:
            return 500, {"message": "Error checking administrative privileges. Please try again."}

        if action not in ["approve", "reject", "publish"]:
            return 400, {"message": "Invalid action. Must be one of: approve, reject, publish."}

        if action == "approve":
            try:
                if community_article.status != CommunityArticle.SUBMITTED:
                    return 400, {"message": "This article is not in the submitted state."}

                try:
                    with transaction.atomic():
                        try:
                            reviewers = community_article.community.reviewers.order_by("?")
                            moderators = community_article.community.moderators.order_by("?")
                        except Exception:
                            return 500, {"message": "Error retrieving reviewers and moderators. Please try again."}

                        if not reviewers.exists() and not moderators.exists():
                            try:
                                # If there are no reviewers and no moderators,
                                # accept the article immediately
                                community_article.status = CommunityArticle.ACCEPTED
                                community_article.save()
                                # TODO: Send notification to the article submitter about
                                # immediate acceptance
                                return 200, {
                                    "message": "Article automatically accepted due to lack of "
                                    "reviewers and moderators."
                                }
                            except Exception:
                                return 500, {"message": "Error updating article status. Please try again."}

                        try:
                            community_article.status = CommunityArticle.UNDER_REVIEW
                            community_article.save()
                        except Exception:
                            return 500, {"message": "Error updating article status. Please try again."}

                        try:
                            # Assign up to 3 reviewers, or all available if less than 3
                            assigned_reviewers = reviewers[:3]
                            community_article.assigned_reviewers.set(assigned_reviewers)
                        except Exception:
                            return 500, {"message": "Error assigning reviewers. Please try again."}

                        try:
                            # Assign one moderator if available
                            if moderators.exists():
                                community_article.assigned_moderator = moderators.first()
                        except Exception:
                            return 500, {"message": "Error assigning moderator. Please try again."}

                        try:
                            community_article.save()
                        except Exception:
                            return 500, {"message": "Error saving article changes. Please try again."}

                        # TODO: Send notifications to assigned reviewers and moderator

                        if not assigned_reviewers and not community_article.assigned_moderator:
                            try:
                                # If no reviewers or moderators were assigned, accept the article
                                community_article.status = CommunityArticle.ACCEPTED
                                community_article.save()
                                # TODO: Send notification to the article submitter about
                                # immediate acceptance
                                return 200, {
                                    "message": "Article automatically accepted due to lack of "
                                    "available reviewers and moderators."
                                }
                            except Exception:
                                return 500, {"message": "Error updating article status. Please try again."}
                except Exception:
                    return 500, {"message": "Error processing approval workflow. Please try again."}

                return 200, {
                    "message": (
                        f"Article approved and assigned for review. "
                        f"Assigned {len(assigned_reviewers)} reviewer(s) and "
                        f"{1 if community_article.assigned_moderator else 0} moderator(s)."
                    )
                }
            except Exception:
                return 500, {"message": "Error approving article. Please try again."}

        elif action == "reject":
            try:
                if community_article.status not in [
                    CommunityArticle.SUBMITTED,
                    CommunityArticle.UNDER_REVIEW,
                ]:
                    return 400, {
                        "message": "This article cannot be rejected in its current state."
                    }

                try:
                    with transaction.atomic():
                        try:
                            community_article.status = CommunityArticle.REJECTED
                            community_article.save()
                        except Exception:
                            return 500, {"message": "Error updating article status. Please try again."}

                        # TODO: Send notification to the article submitter
                except Exception:
                    return 500, {"message": "Error processing rejection workflow. Please try again."}

                return 200, {"message": "Article rejected."}
            except Exception:
                return 500, {"message": "Error rejecting article. Please try again."}

        elif action == "publish":
            try:
                if community_article.status != CommunityArticle.ACCEPTED:
                    return 400, {"message": "This article is not in the accepted state."}

                try:
                    with transaction.atomic():
                        try:
                            community_article.status = CommunityArticle.PUBLISHED
                            community_article.save()
                        except Exception:
                            return 500, {"message": "Error updating article status. Please try again."}

                        # TODO: Send notifications to relevant parties
                        # (submitter, community members, etc.)
                except Exception:
                    return 500, {"message": "Error processing publication workflow. Please try again."}

                return 200, {"message": "Article published successfully."}
            except Exception:
                return 500, {"message": "Error publishing article. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Assessor related API endpoints to assess articles
"""


@router.get(
    "/{community_id}/assigned-articles/",
    response={200: List[ArticleOut], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_assigned_articles(
    request,
    community_id: int,
):
    try:
        user = request.auth
        
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        try:
            if not community.is_member(user):
                return 403, {"message": "You are not a member of this community."}
        except Exception:
            return 500, {"message": "Error checking community membership. Please try again."}

        try:
            role = (
                "reviewer" if community.reviewers.filter(id=user.id).exists() else "moderator"
            )
        except Exception:
            return 500, {"message": "Error determining user role. Please try again."}

        try:
            if role == "reviewer":
                if not community.reviewers.filter(id=user.id).exists():
                    return 403, {"message": "You are not a reviewer in this community."}

                try:
                    assigned_articles = Article.objects.filter(
                        communityarticle__community=community,
                        communityarticle__assigned_reviewers=user,
                        communityarticle__status=CommunityArticle.UNDER_REVIEW,
                    ).distinct()
                except Exception:
                    return 500, {"message": "Error retrieving assigned articles. Please try again."}
            else:  # moderator
                if not community.moderators.filter(id=user.id).exists():
                    return 403, {"message": "You are not a moderator in this community."}

                try:
                    assigned_articles = Article.objects.filter(
                        communityarticle__community=community,
                        communityarticle__assigned_moderator=user,
                        communityarticle__status=CommunityArticle.UNDER_REVIEW,
                    ).distinct()
                except Exception:
                    return 500, {"message": "Error retrieving assigned articles. Please try again."}
        except Exception:
            return 500, {"message": "Error checking user role permissions. Please try again."}

        try:
            return 200, [
                ArticleOut.from_orm_with_custom_fields(article, community, user)
                for article in assigned_articles
            ]
        except Exception:
            return 500, {"message": "Error formatting article data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/{community_article_id}/approve/",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def approve_article(request, community_article_id: int):
    try:
        user = request.auth
        
        try:
            community_article = CommunityArticle.objects.get(id=community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not (
                community_article.assigned_reviewers.filter(id=user.id).exists()
                or community_article.assigned_moderator == user
            ):
                return 403, {"message": "You are not assigned to review this article."}
        except Exception:
            return 500, {"message": "Error checking reviewer assignment. Please try again."}

        try:
            review = Review.objects.filter(
                community_article=community_article, user=user
            ).first()
            if not review:
                return 400, {"message": "You need to submit a review before approving."}
        except Exception:
            return 500, {"message": "Error retrieving review information. Please try again."}

        try:
            with transaction.atomic():
                try:
                    review.is_approved = True
                    review.save()
                except Exception:
                    return 500, {"message": "Error saving review approval. Please try again."}

                try:
                    assigned_reviewer_count = community_article.assigned_reviewers.count()
                    assigned_moderator = community_article.assigned_moderator
                except Exception:
                    return 500, {"message": "Error retrieving article assignments. Please try again."}

                if user == assigned_moderator:
                    try:
                        if assigned_reviewer_count == 0:
                            try:
                                community_article.status = CommunityArticle.ACCEPTED
                                community_article.save()
                                # TODO: Notify author of acceptance
                                return 200, {"message": "Article approved and accepted by moderator."}
                            except Exception:
                                return 500, {"message": "Error updating article status. Please try again."}
                        else:
                            try:
                                all_reviewers_approved = (
                                    Review.objects.filter(
                                        community_article=community_article,
                                        user__in=community_article.assigned_reviewers.all(),
                                        is_approved=True,
                                    ).count()
                                    == assigned_reviewer_count
                                )
                            except Exception:
                                return 500, {"message": "Error checking reviewer approvals. Please try again."}
                                
                            if all_reviewers_approved:
                                try:
                                    community_article.status = CommunityArticle.ACCEPTED
                                    community_article.save()
                                except Exception:
                                    return 500, {"message": "Error updating article status. Please try again."}
                                    
                                # TODO: Notify author of acceptance
                                return 200, {
                                    "message": "Article approved and accepted by moderator "
                                    "after all reviewers' approval."
                                }
                            else:
                                return 200, {
                                    "message": "Moderator approval recorded. Waiting for "
                                    "all reviewers to approve."
                                }
                    except Exception:
                        return 500, {"message": "Error processing moderator approval. Please try again."}
                else:  # User is a reviewer
                    try:
                        try:
                            all_reviewers_approved = (
                                Review.objects.filter(
                                    community_article=community_article,
                                    user__in=community_article.assigned_reviewers.all(),
                                    is_approved=True,
                                ).count()
                                == assigned_reviewer_count
                            )
                        except Exception:
                            return 500, {"message": "Error checking reviewer approvals. Please try again."}

                        if all_reviewers_approved:
                            if assigned_moderator:
                                # TODO: Notify moderator that they can now review
                                return 200, {
                                    "message": "All reviewers have approved. Waiting "
                                    "for moderator's decision."
                                }
                            else:
                                try:
                                    community_article.status = CommunityArticle.ACCEPTED
                                    community_article.save()
                                except Exception:
                                    return 500, {"message": "Error updating article status. Please try again."}
                                    
                                # TODO: Notify author of acceptance
                                return 200, {
                                    "message": "Article approved and accepted by all reviewers."
                                }
                        else:
                            return 200, {
                                "message": "Approval recorded. Waiting for other reviewers."
                            }
                    except Exception:
                        return 500, {"message": "Error processing reviewer approval. Please try again."}
        except Exception:
            return 500, {"message": "Error processing approval. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{community_article_id}/pseudonymous/",
    response={200: CommunityArticlePseudonymousOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def is_article_pseudonymous(request, community_article_id: int):
    try:
        user = request.auth
        
        try:
            community_article = CommunityArticle.objects.select_related("article").get(article__id=community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found in community."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception:
            return 500, {"message": "Error checking administrative privileges. Please try again."}
        
        return 200, {"is_pseudonymous": community_article.is_pseudonymous}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}

@router.post(
    "/{community_article_id}/pseudonymous/",
    response={200: Message, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def toggle_article_pseudonymous(request, community_article_id: int, pseudonymous: bool):
    try:
        user = request.auth
        
        try:
            community_article = CommunityArticle.objects.select_related("article").get(article__id=community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found in community."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception:
            return 500, {"message": "Error checking administrative privileges. Please try again."}
        
        try:
            community_article.is_pseudonymous = pseudonymous
            community_article.save()
        except Exception:
            return 500, {"message": "Error updating article setting. Please try again."}

        return 200, {"message": f"Article reviews and discussions are {'pseudonymous' if pseudonymous else 'non-pseudonymous'} from now on."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}