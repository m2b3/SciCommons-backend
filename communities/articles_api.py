import logging
from typing import List, Literal, Optional

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Exists, OuterRef, Q
from ninja import Query, Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article, Review
from articles.schemas import (
    ArticleOut,
    ArticlesListOut,
    PaginatedArticlesListResponse,
    PaginatedArticlesResponse,
)
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

# Module-level logger
logger = logging.getLogger(__name__)


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
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            # Check if the article is already submitted to the community
            if CommunityArticle.objects.filter(
                article=article, community=community
            ).exists():
                return 400, {
                    "message": "This article is already submitted to this community."
                }
        except Exception as e:
            logger.error(f"Error checking article submission status: {e}")
            return 500, {
                "message": "Error checking article submission status. Please try again."
            }

        try:
            community_article_status = (
                CommunityArticle.PUBLISHED
                if community.type in {"private", "hidden"}
                or community.admins.filter(id=user.id).exists()
                else CommunityArticle.SUBMITTED
            )

            CommunityArticle.objects.create(
                article=article, community=community, status=community_article_status
            )
        except Exception as e:
            logger.error(f"Error submitting article to community: {e}")
            return 500, {
                "message": "Error submitting article to community. Please try again."
            }

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
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            # Continue even if notification fails
            pass

        return 200, {"message": "Article submitted successfully"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/articles/my-articles/",
    response={
        200: PaginatedArticlesListResponse,
        codes_4xx: Message,
        codes_5xx: Message,
    },
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
            articles = Article.objects.filter(submitter=user).select_related(
                "submitter"
            )
        except Exception as e:
            logger.error(f"Error retrieving your articles: {e}")
            return 500, {"message": "Error retrieving your articles. Please try again."}

        try:
            if status_filter:
                subquery = CommunityArticle.objects.filter(article=OuterRef("pk"))
                if status_filter == StatusFilter.PUBLISHED:
                    # Filter articles that are published in any community
                    articles = articles.filter(
                        Exists(subquery.filter(status=CommunityArticle.PUBLISHED))
                    )
                elif status_filter == StatusFilter.UNSUBMITTED:
                    # Filter articles that are not submitted to any community
                    articles = articles.filter(~Exists(subquery))
                elif status_filter == StatusFilter.UNDER_REVIEW:
                    # Filter articles that are under review in any community
                    articles = articles.filter(
                        Exists(subquery.filter(status=CommunityArticle.UNDER_REVIEW))
                    )
                elif status_filter == StatusFilter.ACCEPTED:
                    # Filter articles that are accepted in any community
                    articles = articles.filter(
                        Exists(subquery.filter(status=CommunityArticle.ACCEPTED))
                    )
                elif status_filter == StatusFilter.REJECTED:
                    # Filter articles that are rejected in any community
                    articles = articles.filter(
                        Exists(subquery.filter(status=CommunityArticle.REJECTED))
                    )
        except Exception:
            return 500, {"message": "Error filtering articles. Please try again."}

        # Ordering by most recent first
        articles = articles.order_by("-created_at")

        try:
            paginator = Paginator(articles, limit)
            paginated_articles = paginator.get_page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        try:
            article_ids = [a.id for a in paginated_articles]

            # Prefetch Ratings
            ratings = (
                Review.objects.filter(article_id__in=article_ids)
                .values("article_id")
                .annotate(avg_rating=Avg("rating"))
            )
            ratings_map = {
                r["article_id"]: round(r["avg_rating"] or 0, 1) for r in ratings
            }

            # Prefetch Community Articles (first community article per article)
            community_articles = (
                CommunityArticle.objects.select_related("community")
                .filter(article_id__in=article_ids)
                .order_by("id")
            )

            community_map = {}
            for ca in community_articles:
                if ca.article_id not in community_map:
                    community_map[ca.article_id] = ca  # Pick first occurrence

            response_items = [
                ArticlesListOut.from_orm_with_fields(
                    article=article,
                    total_ratings=ratings_map.get(article.id, 0),
                    community_article=community_map.get(article.id),
                )
                for article in paginated_articles
            ]

            return 200, PaginatedArticlesListResponse(
                items=response_items,
                total=paginator.count,
                page=page,
                per_page=limit,
                num_pages=paginator.num_pages,
            )
        except Exception as e:
            logger.error(f"Error formatting article data: {e}")
            return 500, {"message": "Error formatting article data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Community Admin related API endpoints to manage articles
"""


@router.get(
    "/communities/{community_name}/articles/",
    response={
        200: PaginatedArticlesListResponse,
        codes_4xx: Message,
        codes_5xx: Message,
    },
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
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        try:
            # Start with articles for the specific community
            queryset = (
                Article.objects.filter(communityarticle__community=community)
                .select_related("submitter")
                .distinct()
            )

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
        except Exception as e:
            logger.error(f"Error filtering articles: {e}")
            return 500, {"message": "Error filtering articles. Please try again."}

        try:
            # Sorting
            allowed_sort_fields = ["submitted_at", "published_at", "created_at"]
            if sort_by not in allowed_sort_fields:
                return 400, {"message": f"Invalid sort_by field: {sort_by}"}

            sort_field = (
                f"communityarticle__{sort_by}"
                if sort_by in ["submitted_at", "published_at"]
                else sort_by
            )
            sort_prefix = "-" if sort_order.lower() == "desc" else ""
            queryset = queryset.order_by(f"{sort_prefix}{sort_field}")
        except Exception as e:
            logger.error(f"Error sorting articles: {e}")
            return 500, {"message": "Error sorting articles. Please try again."}

        try:
            # Pagination
            paginator = Paginator(queryset, size)
            paginated_articles = paginator.get_page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        # current_user: Optional[User] = None if not request.auth else request.auth

        try:
            # Prefetch CommunityArticle & Ratings for these articles
            article_ids = [a.id for a in paginated_articles]

            # First CommunityArticle per article (since we already filter by community)
            community_articles = (
                CommunityArticle.objects.filter(
                    article_id__in=article_ids, community=community
                )
                .select_related("community")
                .order_by("id")
            )
            community_map = {ca.article_id: ca for ca in community_articles}

            # Ratings
            ratings = (
                Review.objects.filter(article_id__in=article_ids)
                .values("article_id")
                .annotate(avg_rating=Avg("rating"))
            )
            ratings_map = {
                r["article_id"]: round(r["avg_rating"] or 0, 1) for r in ratings
            }

            response_items = [
                ArticlesListOut.from_orm_with_fields(
                    article=article,
                    total_ratings=ratings_map.get(article.id, 0),
                    community_article=community_map.get(article.id),
                )
                for article in paginated_articles
            ]

            return 200, PaginatedArticlesListResponse(
                items=response_items,
                total=paginator.count,
                page=page,
                per_page=size,
                num_pages=paginator.num_pages,
            )
        except Exception as e:
            logger.error(f"Error formatting article data: {e}")
            return 500, {"message": "Error formatting article data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception as e:
            logger.error(f"Error checking administrative privileges: {e}")
            return 500, {
                "message": "Error checking administrative privileges. Please try again."
            }

        if action not in ["approve", "reject", "publish"]:
            return 400, {
                "message": "Invalid action. Must be one of: approve, reject, publish."
            }

        if action == "approve":
            try:
                if community_article.status != CommunityArticle.SUBMITTED:
                    return 400, {
                        "message": "This article is not in the submitted state."
                    }

                try:
                    with transaction.atomic():
                        try:
                            reviewers = community_article.community.reviewers.order_by(
                                "?"
                            )
                            moderators = (
                                community_article.community.moderators.order_by("?")
                            )
                        except Exception as e:
                            logger.error(
                                f"Error retrieving reviewers and moderators: {e}"
                            )
                            return 500, {
                                "message": "Error retrieving reviewers and moderators. Please try again."
                            }

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
                            except Exception as e:
                                logger.error(f"Error updating article status: {e}")
                                return 500, {
                                    "message": "Error updating article status. Please try again."
                                }

                        try:
                            community_article.status = CommunityArticle.UNDER_REVIEW
                            community_article.save()
                        except Exception as e:
                            logger.error(f"Error updating article status: {e}")
                            return 500, {
                                "message": "Error updating article status. Please try again."
                            }

                        try:
                            # Assign up to 3 reviewers, or all available if less than 3
                            assigned_reviewers = reviewers[:3]
                            community_article.assigned_reviewers.set(assigned_reviewers)
                        except Exception as e:
                            logger.error(f"Error assigning reviewers: {e}")
                            return 500, {
                                "message": "Error assigning reviewers. Please try again."
                            }

                        try:
                            # Assign one moderator if available
                            if moderators.exists():
                                community_article.assigned_moderator = (
                                    moderators.first()
                                )
                        except Exception as e:
                            logger.error(f"Error assigning moderator: {e}")
                            return 500, {
                                "message": "Error assigning moderator. Please try again."
                            }

                        try:
                            community_article.save()
                        except Exception as e:
                            logger.error(f"Error saving article changes: {e}")
                            return 500, {
                                "message": "Error saving article changes. Please try again."
                            }

                        # TODO: Send notifications to assigned reviewers and moderator

                        if (
                            not assigned_reviewers
                            and not community_article.assigned_moderator
                        ):
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
                            except Exception as e:
                                logger.error(f"Error updating article status: {e}")
                                return 500, {
                                    "message": "Error updating article status. Please try again."
                                }
                except Exception as e:
                    logger.error(f"Error processing approval workflow: {e}")
                    return 500, {
                        "message": "Error processing approval workflow. Please try again."
                    }

                return 200, {
                    "message": (
                        f"Article approved and assigned for review. "
                        f"Assigned {len(assigned_reviewers)} reviewer(s) and "
                        f"{1 if community_article.assigned_moderator else 0} moderator(s)."
                    )
                }
            except Exception as e:
                logger.error(f"Error approving article: {e}")
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
                        except Exception as e:
                            logger.error(f"Error updating article status: {e}")
                            return 500, {
                                "message": "Error updating article status. Please try again."
                            }

                        # TODO: Send notification to the article submitter
                except Exception as e:
                    logger.error(f"Error processing rejection workflow: {e}")
                    return 500, {
                        "message": "Error processing rejection workflow. Please try again."
                    }

                return 200, {"message": "Article rejected."}
            except Exception as e:
                logger.error(f"Error rejecting article: {e}")
                return 500, {"message": "Error rejecting article. Please try again."}

        elif action == "publish":
            try:
                if community_article.status != CommunityArticle.ACCEPTED:
                    return 400, {
                        "message": "This article is not in the accepted state."
                    }

                try:
                    with transaction.atomic():
                        try:
                            community_article.status = CommunityArticle.PUBLISHED
                            community_article.save()
                        except Exception as e:
                            logger.error(f"Error updating article status: {e}")
                            return 500, {
                                "message": "Error updating article status. Please try again."
                            }

                        # TODO: Send notifications to relevant parties
                        # (submitter, community members, etc.)
                except Exception as e:
                    logger.error(f"Error processing publication workflow: {e}")
                    return 500, {
                        "message": "Error processing publication workflow. Please try again."
                    }

                return 200, {"message": "Article published successfully."}
            except Exception as e:
                logger.error(f"Error publishing article: {e}")
                return 500, {"message": "Error publishing article. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Assessor related API endpoints to assess articles
"""


@router.get(
    "/{community_id}/assigned-articles/",
    response={200: List[ArticlesListOut], codes_4xx: Message, codes_5xx: Message},
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
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        if not community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            is_reviewer = community.reviewers.filter(id=user.id).exists()
            is_moderator = community.moderators.filter(id=user.id).exists()

            if not (is_reviewer or is_moderator):
                return 403, {
                    "message": "You are not assigned any review roles in this community."
                }
        except Exception as e:
            logger.error(f"Error determining user role: {e}")
            return 500, {"message": "Error determining user role. Please try again."}

        try:
            role_filter = Q()
            if is_reviewer:
                role_filter = Q(communityarticle__assigned_reviewers=user)
            elif is_moderator:
                role_filter = Q(communityarticle__assigned_moderator=user)

            assigned_articles = (
                Article.objects.filter(
                    Q(communityarticle__community=community),
                    Q(communityarticle__status=CommunityArticle.UNDER_REVIEW),
                    role_filter,
                )
                .select_related("submitter")
                .distinct()
            )
        except Exception as e:
            logger.error(f"Error retrieving assigned articles: {e}")
            return 500, {
                "message": "Error retrieving assigned articles. Please try again."
            }

        try:
            article_ids = [a.id for a in assigned_articles]

            community_articles = {
                ca.article_id: ca
                for ca in CommunityArticle.objects.filter(
                    article_id__in=article_ids,
                    community=community,
                    status=CommunityArticle.UNDER_REVIEW,
                ).select_related("community", "article")
            }

            response = [
                ArticlesListOut.from_orm_with_fields(
                    article=article,
                    total_ratings=0.0,  # Optionally fetch rating if needed
                    community_article=community_articles.get(article.id),
                )
                for article in assigned_articles
            ]
            return 200, response
        except Exception as e:
            logger.error(f"Error formatting article data: {e}")
            return 500, {"message": "Error formatting article data. Please try again."}

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not (
                community_article.assigned_reviewers.filter(id=user.id).exists()
                or community_article.assigned_moderator == user
            ):
                return 403, {"message": "You are not assigned to review this article."}
        except Exception as e:
            logger.error(f"Error checking reviewer assignment: {e}")
            return 500, {
                "message": "Error checking reviewer assignment. Please try again."
            }

        try:
            review = Review.objects.filter(
                community_article=community_article, user=user
            ).first()
            if not review:
                return 400, {"message": "You need to submit a review before approving."}
        except Exception as e:
            logger.error(f"Error retrieving review information: {e}")
            return 500, {
                "message": "Error retrieving review information. Please try again."
            }

        try:
            with transaction.atomic():
                try:
                    review.is_approved = True
                    review.save()
                except Exception as e:
                    logger.error(f"Error saving review approval: {e}")
                    return 500, {
                        "message": "Error saving review approval. Please try again."
                    }

                try:
                    assigned_reviewer_count = (
                        community_article.assigned_reviewers.count()
                    )
                    assigned_moderator = community_article.assigned_moderator
                except Exception as e:
                    logger.error(f"Error retrieving article assignments: {e}")
                    return 500, {
                        "message": "Error retrieving article assignments. Please try again."
                    }

                if user == assigned_moderator:
                    try:
                        if assigned_reviewer_count == 0:
                            try:
                                community_article.status = CommunityArticle.ACCEPTED
                                community_article.save()
                                # TODO: Notify author of acceptance
                                return 200, {
                                    "message": "Article approved and accepted by moderator."
                                }
                            except Exception as e:
                                logger.error(f"Error updating article status: {e}")
                                return 500, {
                                    "message": "Error updating article status. Please try again."
                                }
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
                            except Exception as e:
                                logger.error(f"Error checking reviewer approvals: {e}")
                                return 500, {
                                    "message": "Error checking reviewer approvals. Please try again."
                                }

                            if all_reviewers_approved:
                                try:
                                    community_article.status = CommunityArticle.ACCEPTED
                                    community_article.save()
                                except Exception as e:
                                    logger.error(f"Error updating article status: {e}")
                                    return 500, {
                                        "message": "Error updating article status. Please try again."
                                    }

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
                    except Exception as e:
                        logger.error(f"Error processing moderator approval: {e}")
                        return 500, {
                            "message": "Error processing moderator approval. Please try again."
                        }
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
                        except Exception as e:
                            logger.error(f"Error checking reviewer approvals: {e}")
                            return 500, {
                                "message": "Error checking reviewer approvals. Please try again."
                            }

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
                                except Exception as e:
                                    logger.error(f"Error updating article status: {e}")
                                    return 500, {
                                        "message": "Error updating article status. Please try again."
                                    }

                                # TODO: Notify author of acceptance
                                return 200, {
                                    "message": "Article approved and accepted by all reviewers."
                                }
                        else:
                            return 200, {
                                "message": "Approval recorded. Waiting for other reviewers."
                            }
                    except Exception as e:
                        logger.error(f"Error processing reviewer approval: {e}")
                        return 500, {
                            "message": "Error processing reviewer approval. Please try again."
                        }
        except Exception as e:
            logger.error(f"Error processing approval: {e}")
            return 500, {"message": "Error processing approval. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{community_article_id}/pseudonymous/",
    response={
        200: CommunityArticlePseudonymousOut,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def is_article_pseudonymous(request, community_article_id: int):
    try:
        user = request.auth

        try:
            community_article = CommunityArticle.objects.select_related("article").get(
                article__id=community_article_id
            )
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found in community."}
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception as e:
            logger.error(f"Error checking administrative privileges: {e}")
            return 500, {
                "message": "Error checking administrative privileges. Please try again."
            }

        return 200, {"is_pseudonymous": community_article.is_pseudonymous}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
            community_article = CommunityArticle.objects.select_related("article").get(
                article__id=community_article_id
            )
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Article not found in community."}
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            if not community_article.community.is_admin(user):
                return 403, {"message": "You are not an admin of this community."}
        except Exception as e:
            logger.error(f"Error checking administrative privileges: {e}")
            return 500, {
                "message": "Error checking administrative privileges. Please try again."
            }

        try:
            community_article.is_pseudonymous = pseudonymous
            community_article.save()
        except Exception as e:
            logger.error(f"Error updating article setting: {e}")
            return 500, {"message": "Error updating article setting. Please try again."}

        return 200, {
            "message": f"Article reviews and discussions are {'pseudonymous' if pseudonymous else 'non-pseudonymous'} from now on."
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
