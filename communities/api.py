from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from ninja import File, Form, Router, UploadedFile
from ninja.errors import HttpRequest
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from communities.models import Community, JoinRequest
from communities.schemas import (
    CommunityDetails,
    CreateCommunityResponse,
    CreateCommunitySchema,
    Message,
    PaginatedCommunitySchema,
    UpdateCommunityDetails,
)
from users.auth import JWTAuth, OptionalJWTAuth

router = Router(tags=["Communities"])


"""
Community Management Endpoints
"""


@router.get(
    "/community/{community_name}/",
    response={200: CommunityDetails, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_community(request, community_name: str):
    try:
        community = Community.objects.get(name=community_name)

        num_published_articles = Article.objects.filter(
            community=community, published=True
        ).count()
        num_articles = Article.objects.filter(community=community).count()

        num_members = community.members.count()
        num_moderators = community.moderators.count()
        num_reviewers = community.reviewers.count()

        response_data = CommunityDetails(
            id=community.id,
            name=community.name,
            description=community.description,
            tags=community.tags,
            type=community.type,
            profile_pic_url=community.profile_pic_url,
            banner_pic_url=community.banner_pic_url,
            slug=community.slug,
            created_at=community.created_at,
            rules=community.rules,
            num_moderators=num_moderators,
            num_reviewers=num_reviewers,
            num_members=num_members,
            num_published_articles=num_published_articles,
            num_articles=num_articles,
        )

        user = request.auth

        if not isinstance(user, bool):
            response_data.is_member = community.members.filter(id=user.id).exists()
            response_data.is_moderator = community.moderators.filter(
                id=user.id
            ).exists()
            response_data.is_reviewer = community.reviewers.filter(id=user.id).exists()
            response_data.is_admin = community.admins.filter(id=user.id).exists()

            # Check if the user has a latest join request
            join_request = JoinRequest.objects.filter(
                community=community, user=user
            ).order_by("-id")

            if join_request.exists():
                print(join_request.first().status)
                response_data.join_request_status = join_request.first().status

        return response_data
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/",
    response={200: PaginatedCommunitySchema, codes_4xx: Message, codes_5xx: Message},
)
def list_communities(request: HttpRequest, page: int = 1, limit: int = 10):
    try:
        if page < 1 or limit < 1:
            return 400, {"message": "Invalid page or limit."}

        communities = Community.objects.filter(~Q(type="hidden"))

        paginator = Paginator(communities, limit)
        paginated_communities = paginator.get_page(page)

        # Todo: Modify and return the fields required for the response
        results = [
            CommunityDetails(
                id=community.id,
                name=community.name,
                description=community.description,
                tags=community.tags,
                type=community.type,
                profile_pic_url=community.profile_pic_url,
                banner_pic_url=community.banner_pic_url,
                slug=community.slug,
                created_at=community.created_at,
                rules=community.rules,
                num_moderators=community.moderators.count(),
                num_reviewers=community.reviewers.count(),
                num_members=community.members.count(),
                num_published_articles=Article.objects.filter(
                    community=community, published=True
                ).count(),
                num_articles=Article.objects.filter(community=community).count(),
            )
            for community in paginated_communities.object_list
        ]

        return 200, {
            "total": paginator.count,
            "page": paginated_communities.number,
            "size": paginator.per_page,
            "communities": results,
        }
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/",
    response={200: CreateCommunityResponse, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_community(
    request: HttpRequest,
    payload: Form[CreateCommunitySchema],
    profile_image_file: File[UploadedFile] = None,
):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth

        # Todo: Check if the user already has a community
        if Community.objects.filter(admins=user).exists():
            return 400, {"message": "You can only create one community."}

        # Process the uploaded profile image file
        profile_image_file = profile_image_file if profile_image_file else None

        # Validate the provided data and create a new Community
        new_community = Community.objects.create(
            name=payload.name,
            description=payload.description,
            tags=payload.tags,
            type=payload.type,
            profile_pic_url=profile_image_file,
        )
        # # new_community.full_clean()  # Validate fields

        # Todo: Create a membership for the creator
        # Membership.objects.create(user=user, community=new_community)

        new_community.admins.add(user)  # Add the creator as an admin

        return CreateCommunityResponse(
            id=new_community.id, message="Community created successfully."
        )

    except ValidationError as e:
        return 400, {"message": str(e)}
    except Exception as e:
        return 500, {"message": str(e)}


@router.patch(
    "/{community_id}/",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_community(
    request: HttpRequest,
    community_id: int,
    payload: Form[UpdateCommunityDetails],
    profile_pic_file: File[UploadedFile] = None,
    banner_pic_file: File[UploadedFile] = None,
):
    try:
        community = Community.objects.get(id=community_id)

        # Check if the user is an admin of this community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have permission to modify this community."
            }

        # Update fields
        if payload.description:
            community.description = payload.description
        if payload.type:
            community.type = payload.type
        if payload.tags:
            community.tags = payload.tags
        if payload.rules:
            community.rules = payload.rules

        if banner_pic_file:
            community.banner_pic_url = banner_pic_file

        if profile_pic_file:
            community.profile_pic_url = profile_pic_file

        community.save()

        return 200, {"message": "Community details updated successfully."}

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except ValidationError as e:
        return 400, {"message": str(e)}
    except Exception as e:
        return {"error": str(e)}, 500


@router.delete("/{community_id}/", response={204: None}, auth=JWTAuth())
def delete_community(request: HttpRequest, community_id: int):
    try:
        community = Community.objects.get(id=community_id)

        # Check if the user is an admin of this community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have permission to delete this community."
            }

        # Delete the community
        community.delete()

        # Return a 204 (No Content) status to indicate successful deletion
        return None, 204

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}
