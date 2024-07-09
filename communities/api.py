from django.core.paginator import Paginator
from django.db.models import Q
from ninja import File, Router, UploadedFile
from ninja.errors import HttpRequest

from communities.models import Community
from communities.schemas import (
    CommunityCreateSchema,
    CommunitySchema,
    CommunityUpdateSchema,
    PaginatedCommunities,
)
from myapp.schemas import Message
from users.auth import JWTAuth, OptionalJWTAuth

router = Router(tags=["Communities"])


"""
Community Management Endpoints
"""


@router.post(
    "/communities/",
    response={201: CommunitySchema, 400: Message, 500: Message},
    auth=JWTAuth(),
)
def create_community(
    request: HttpRequest,
    payload: CommunityCreateSchema,
    profile_image_file: File[UploadedFile] = None,
):
    # Retrieve the authenticated user from the JWT token
    user = request.auth

    if Community.objects.filter(admins=user).exists():
        return 400, {"message": "You can only create one community."}

    # Validate the provided data and create a new Community
    new_community = Community.objects.create(
        name=payload.details.name,
        description=payload.details.description,
        tags=payload.details.tags,
        type=payload.details.type,
        profile_pic_url=profile_image_file,
    )
    # new_community.full_clean()  # Validate fields

    new_community.admins.add(user)  # Add the creator as an admin
    new_community.members.add(user)  # Add the creator as a member

    return 201, CommunitySchema.from_orm_with_custom_fields(new_community, user)


@router.get(
    "/",
    response={
        200: PaginatedCommunities,
        400: Message,
        500: Message,
    },
)
def list_communities(request: HttpRequest, page: int = 1, limit: int = 10):
    communities = Community.objects.filter(~Q(type="hidden")).order_by("-created_at")

    paginator = Paginator(communities, limit)
    paginated_communities = paginator.get_page(page)

    results = [
        CommunitySchema.from_orm_with_custom_fields(community)
        for community in paginated_communities.object_list
    ]

    return 200, PaginatedCommunities(
        items=results, total=paginator.count, page=page, per_page=limit
    )


@router.get(
    "/community/{community_name}/",
    response={200: CommunitySchema, 400: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def get_community(request, community_name: str):
    community = Community.objects.get(name=community_name)
    user = request.auth
    return 200, CommunitySchema.from_orm_with_custom_fields(community, user)


@router.put(
    "/{community_id}/",
    response={200: Message, 400: Message, 500: Message},
    auth=JWTAuth(),
)
def update_community(
    request: HttpRequest,
    community_id: int,
    payload: CommunityUpdateSchema,
    profile_pic_file: File[UploadedFile] = None,
    banner_pic_file: File[UploadedFile] = None,
):
    community = Community.objects.get(id=community_id)

    # Check if the user is an admin of this community
    if not community.admins.filter(id=request.auth.id).exists():
        return 403, {"message": "You do not have permission to modify this community."}

    # Update fields
    community.description = payload.details.description
    community.type = payload.details.type
    # Make tags JSON serializable
    community.tags = [tag.dict() for tag in payload.details.tags]
    community.rules = payload.details.rules

    if banner_pic_file:
        community.banner_pic_url = banner_pic_file
    if profile_pic_file:
        community.profile_pic_url = profile_pic_file

    community.save()

    return 200, {"message": "Community details updated successfully."}


@router.delete("/{community_id}/", response={204: None}, auth=JWTAuth())
def delete_community(request: HttpRequest, community_id: int):
    community = Community.objects.get(id=community_id)

    # Check if the user is an admin of this community
    if not community.admins.filter(id=request.auth.id).exists():
        return 403, {"message": "You do not have permission to delete this community."}

    # Todo: Do not delete the community, just mark it as deleted
    community.delete()

    return 204, None
