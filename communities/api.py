from datetime import timedelta
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from ninja import File, Query, Router, UploadedFile
from ninja.errors import HttpRequest

# from users.models import Hashtag, HashtagRelation
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Discussion, Review
from articles.schemas import ArticleBasicOut
from communities.models import Community, CommunityArticle
from communities.schemas import (
    CommunityBasicOut,
    CommunityCreateSchema,
    CommunityFilters,
    CommunityListOut,
    CommunityOut,
    CommunityStatsResponse,
    CommunityUpdateSchema,
    PaginatedCommunities,
)
from myapp.constants import COMMUNITY_SETTINGS, COMMUNITY_TYPES_LIST
from myapp.feature_flags import MAX_COMMUNITIES_PER_USER
from myapp.schemas import DateCount, Message
from myapp.utils import validate_tags
from users.auth import JWTAuth, OptionalJWTAuth

router = Router(tags=["Communities"])


"""
Community Management Endpoints
"""


@router.post(
    "/communities/",
    response={201: CommunityOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_community(
    request: HttpRequest,
    payload: CommunityCreateSchema,
    profile_image_file: File[UploadedFile] = None,
):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth

        with transaction.atomic():
            try:
                # Check if the user created communities are less than 5
                if (
                    Community.objects.filter(admins=user).count()
                    >= MAX_COMMUNITIES_PER_USER
                ):
                    return 400, {
                        "message": f"You can only create {MAX_COMMUNITIES_PER_USER} communities."
                    }
            except Exception:
                return 500, {
                    "message": "Error checking your community count. Please try again."
                }

            # validate all tags at once
            # validate_tags(payload.details.tags)

            if payload.details.type not in COMMUNITY_TYPES_LIST:
                return 400, {"message": "Invalid community type."}

            if (
                payload.details.type == Community.PUBLIC
                and payload.details.community_settings
                not in [
                    COMMUNITY_SETTINGS.ANYONE_CAN_JOIN.value,
                    COMMUNITY_SETTINGS.REQUEST_TO_JOIN.value,
                ]
                or payload.details.type == Community.PRIVATE
                and payload.details.community_settings not in [None]
            ):
                return 400, {"message": "Invalid community settings."}

            try:
                # Validate the provided data and create a new Community
                new_community = Community(
                    name=payload.details.name,
                    description=payload.details.description,
                    type=payload.details.type,
                    requires_admin_approval=payload.details.community_settings
                    == COMMUNITY_SETTINGS.REQUEST_TO_JOIN.value
                    or payload.details.type == Community.PRIVATE,
                    community_settings=payload.details.community_settings,
                    # profile_pic_url=profile_image_file,
                )
                new_community.save()
            except Exception:
                return 500, {"message": "Error creating community. Please try again."}

            # Create Tags
            # content_type = ContentType.objects.get_for_model(Community)

            # for hashtag_name in payload.details.tags:
            #     hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
            #     HashtagRelation.objects.create(
            #         hashtag=hashtag, content_type=content_type, object_id=new_community.id
            #     )

            try:
                new_community.admins.add(user)  # Add the creator as an admin
                new_community.members.add(user)  # Add the creator as a member
            except Exception:
                return 500, {
                    "message": "Error setting up community membership. Please try again."
                }

            try:
                return 201, CommunityOut.from_orm_with_custom_fields(
                    new_community, user
                )
            except Exception:
                return 500, {
                    "message": "Community created but error retrieving community data."
                }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/",
    response={
        200: PaginatedCommunities,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    summary="Get Communities",
    auth=OptionalJWTAuth,
)
def list_communities(
    request: HttpRequest,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
):
    try:
        user = request.auth
        try:
            # Start with all non-hidden communities
            communities = Community.objects.filter(~Q(type=Community.HIDDEN))
        except Exception:
            return 500, {"message": "Error retrieving communities. Please try again."}

        # Apply search if provided
        try:
            if search:
                search = search.strip()
                if len(search) > 0:
                    communities = communities.filter(
                        Q(name__icontains=search) | Q(description__icontains=search)
                    )
        except Exception:
            return 500, {"message": "Error processing search query. Please try again."}

        # Apply sorting
        try:
            if sort:
                sort = sort.strip()
                if sort == "latest":
                    communities = communities.order_by("-created_at")
                elif sort == "oldest":
                    communities = communities.order_by("created_at")
                elif sort == "name_asc":
                    communities = communities.order_by("name")
                elif sort == "name_desc":
                    communities = communities.order_by("-name")
                # Add more sorting options if needed
            else:
                # Default sort by latest
                communities = communities.order_by("-created_at")
        except Exception:
            return 500, {"message": "Error sorting communities. Please try again."}

        try:
            paginator = Paginator(communities, per_page)
            paginated_communities = paginator.get_page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        try:
            community_ids = [c.id for c in paginated_communities.object_list]

            # Bulk fetch counts to eliminate N+1
            published_counts = (
                CommunityArticle.objects.filter(
                    community_id__in=community_ids, status=CommunityArticle.PUBLISHED
                )
                .values("community_id")
                .annotate(num_published_articles=Count("id"))
            )
            published_map = {
                c["community_id"]: c["num_published_articles"] for c in published_counts
            }

            members_counts = (
                Community.objects.filter(id__in=community_ids)
                .annotate(num_members=Count("members"))
                .values("id", "num_members")
            )
            members_map = {c["id"]: c["num_members"] for c in members_counts}

            # Build Response
            results = []
            for community in paginated_communities.object_list:
                response_data = {
                    "id": community.id,
                    "name": community.name,
                    "description": community.description,
                    "type": community.type,
                    "slug": community.slug,
                    "created_at": community.created_at,
                    "num_members": members_map.get(community.id, 0),
                    "num_published_articles": published_map.get(community.id, 0),
                }

                # Optional user-specific flags (minimal perf impact here)
                # if user and not isinstance(user, bool):
                #     if community.is_member(user):
                #         response_data["is_member"] = True
                #     elif community.is_admin(user):
                #         response_data["is_admin"] = True
                #     else:
                #         join_request = JoinRequest.objects.filter(
                #             community=community, user=user
                #         ).order_by("-id")
                #         if join_request.exists():
                #             response_data["is_request_sent"] = True
                #             response_data["requested_at"] = (
                #                 join_request.first().requested_at
                #             )

                results.append(CommunityListOut(**response_data))

            return 200, PaginatedCommunities(
                items=results,
                total=paginator.count,
                page=page,
                per_page=per_page,
                num_pages=paginator.num_pages,
            )
        except Exception:
            return 500, {
                "message": "Error formatting community data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/community/{community_name}/",
    response={200: CommunityOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_community(request, community_name: str):
    try:
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        user = request.auth

        if community.type == Community.HIDDEN and not community.is_member(user):
            return 403, {
                "message": "You do not have permission to view this community."
            }

        try:
            return 200, CommunityOut.from_orm_with_custom_fields(community, user)
        except Exception:
            return 500, {
                "message": "Error formatting community data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/{community_id}/",
    response={200: CommunityOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_community(
    request: HttpRequest,
    community_id: int,
    payload: CommunityUpdateSchema,
    profile_pic_file: File[UploadedFile] = None,
    banner_pic_file: File[UploadedFile] = None,
):
    try:
        with transaction.atomic():
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            except Exception:
                return 500, {"message": "Error retrieving community. Please try again."}

            # Check if the user is an admin of this community
            if not community.admins.filter(id=request.auth.id).exists():
                return 403, {
                    "message": "You do not have permission to modify this community."
                }

            try:
                # Update fields
                community.description = payload.details.description
                community.type = payload.details.type
                community.rules = payload.details.rules
                community.community_settings = payload.details.community_settings
                community.requires_admin_approval = (
                    payload.details.community_settings
                    == COMMUNITY_SETTINGS.REQUEST_TO_JOIN.value
                    or payload.details.type == Community.PRIVATE
                )
                # community.about = payload.details.about

                # # Update Tags
                # content_type = ContentType.objects.get_for_model(Community)
                # HashtagRelation.objects.filter(
                #     content_type=content_type, object_id=community.id
                # ).delete()
                # for hashtag_name in payload.details.tags:
                #     hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
                #     HashtagRelation.objects.create(
                #         hashtag=hashtag, content_type=content_type, object_id=community.id
                #     )

                if banner_pic_file:
                    community.banner_pic_url = banner_pic_file
                if profile_pic_file:
                    community.profile_pic_url = profile_pic_file

                community.save()
            except Exception:
                return 500, {"message": "Error updating community. Please try again."}

            try:
                return 200, CommunityOut.from_orm_with_custom_fields(
                    community, request.auth
                )
            except Exception:
                return 500, {
                    "message": "Community updated but error retrieving community data."
                }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/{community_id}/",
    response={204: None, 403: Message, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_community(request: HttpRequest, community_id: int):
    try:
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the user is an admin of this community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have permission to delete this community."
            }

        try:
            # Todo: Do not delete the community, just mark it as deleted
            community.delete()
        except Exception:
            return 500, {"message": "Error deleting community. Please try again."}

        return 204, None
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{community_id}/relevant-communities",
    response={200: List[CommunityBasicOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_relevant_communities(
    request, community_id: int, filters: CommunityFilters = Query(...)
):
    try:
        try:
            base_community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        # Get hashtags of the base community
        try:
            base_hashtags = base_community.hashtags.values_list("hashtag_id", flat=True)
        except Exception:
            return 500, {
                "message": "Error retrieving community tags. Please try again."
            }

        try:
            # Query for relevant communities
            queryset = Community.objects.exclude(id=community_id).exclude(type="hidden")
        except Exception:
            return 500, {"message": "Error retrieving communities. Please try again."}

        try:
            # Calculate relevance score based on shared hashtags
            queryset = queryset.annotate(
                relevance_score=Count(
                    "hashtags", filter=Q(hashtags__hashtag_id__in=base_hashtags)
                )
            ).filter(relevance_score__gt=0)
        except Exception:
            return 500, {
                "message": "Error calculating relevance scores. Please try again."
            }

        try:
            if filters.filter_type == "popular":
                queryset = queryset.annotate(
                    popularity_score=Count("members")
                    + Count(
                        "communityarticle",
                        filter=Q(communityarticle__status="published"),
                    )
                ).order_by("-popularity_score", "-relevance_score")
            elif filters.filter_type == "recent":
                queryset = queryset.order_by("-created_at", "-relevance_score")
            else:  # "relevant" is the default
                queryset = queryset.order_by("-relevance_score", "-created_at")
        except Exception:
            return 500, {"message": "Error sorting communities. Please try again."}

        try:
            communities = queryset[filters.offset : filters.offset + filters.limit]
        except Exception:
            return 400, {"message": "Invalid pagination parameters."}

        try:
            result = [
                CommunityBasicOut.from_orm(community) for community in communities
            ]
            return 200, result
        except Exception:
            return 500, {
                "message": "Error formatting community data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Community Stats Endpoint
"""


@router.get(
    "/{community_slug}/dashboard",
    response={200: CommunityStatsResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_community_dashboard(request, community_slug: str):
    try:
        try:
            community = Community.objects.get(slug=community_slug)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        try:
            # Member stats
            total_members = community.members.count()
            new_members_this_week = community.members.filter(
                membership__joined_at__gte=week_ago
            ).count()
        except Exception:
            return 500, {
                "message": "Error retrieving member statistics. Please try again."
            }

        try:
            # Article stats
            community_articles = CommunityArticle.objects.filter(community=community)
            total_articles = community_articles.count()
            new_articles_this_week = community_articles.filter(
                submitted_at__gte=week_ago
            ).count()
            articles_published = community_articles.filter(status="published").count()
            new_published_articles_this_week = community_articles.filter(
                status="published", published_at__gte=week_ago
            ).count()
        except Exception:
            return 500, {
                "message": "Error retrieving article statistics. Please try again."
            }

        try:
            # Review and discussion stats
            total_reviews = Review.objects.filter(community=community).count()
            total_discussions = Discussion.objects.filter(community=community).count()
        except Exception:
            return 500, {
                "message": "Error retrieving review and discussion statistics. Please try again."
            }

        try:
            # Member growth over time (last 5 days)
            member_growth = []
            for i in range(5):
                date = now - timedelta(days=i)
                count = community.members.filter(
                    membership__joined_at__date__lte=date
                ).count()
                member_growth.append(DateCount(date=date.date(), count=count))
            member_growth.reverse()
        except Exception:
            return 500, {
                "message": "Error calculating member growth trends. Please try again."
            }

        try:
            # Article submission trends (last 5 days)
            article_submission_trends = []
            for i in range(5):
                date = now - timedelta(days=i)
                count = community_articles.filter(submitted_at__date__lte=date).count()
                article_submission_trends.append(
                    DateCount(date=date.date(), count=count)
                )
            article_submission_trends.reverse()
        except Exception:
            return 500, {
                "message": "Error calculating article submission trends. Please try again."
            }

        try:
            # Recently published articles
            recently_published = community_articles.filter(status="published").order_by(
                "-published_at"
            )[
                :5
            ]  # Fetching the 5 most recent articles

            recently_published_articles = [
                ArticleBasicOut.from_orm_with_custom_fields(
                    community_article.article, request.auth
                )
                for community_article in recently_published
            ]
        except Exception:
            return 500, {
                "message": "Error retrieving recently published articles. Please try again."
            }

        try:
            return 200, CommunityStatsResponse(
                name=community.name,
                description=community.description,
                total_members=total_members,
                new_members_this_week=new_members_this_week,
                total_articles=total_articles,
                new_articles_this_week=new_articles_this_week,
                articles_published=articles_published,
                new_published_articles_this_week=new_published_articles_this_week,
                total_reviews=total_reviews,
                total_discussions=total_discussions,
                member_growth=member_growth,
                article_submission_trends=article_submission_trends,
                recently_published_articles=recently_published_articles,
            )
        except Exception:
            return 500, {
                "message": "Error generating dashboard data. Please try again."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}
