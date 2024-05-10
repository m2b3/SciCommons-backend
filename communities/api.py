from datetime import timedelta
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError, HttpRequest

from communities.models import Community, Invitation, JoinRequest, Membership
from communities.schemas import (
    CommunityDetailSchema,
    CommunityMemberSchema,
    CommunitySchema,
    CreateCommunitySchema,
    InviteSchema,
    PaginatedCommunitySchema,
    UpdateCommunitySchema,
)
from users.auth import JWTAuth
from users.models import User

router = Router(auth=JWTAuth())

signer = TimestampSigner()


"""
Community Management Endpoints
"""


@router.get("/", response=PaginatedCommunitySchema)
def list_communities(
    request: HttpRequest, page: Optional[int] = 1, size: Optional[int] = 10
):
    try:
        if page < 1 or size < 1:
            return {"error": "Invalid pagination parameters"}, 400

        offset = (page - 1) * size

        communities = Community.objects.all()[offset : offset + size]

        total_communities = Community.objects.count()

        if not communities:
            raise Http404("No communities found.")

        return PaginatedCommunitySchema(
            total=total_communities,
            page=page,
            size=size,
            results=[CommunitySchema.from_orm(community) for community in communities],
        )
    except Exception as e:
        return {"error": str(e)}, 500


@router.get("/{community_id}/", response=CommunityDetailSchema)
def get_community_detail(request, community_id: int):
    try:
        # Fetch community by id and raise an error if not found
        community = Community.objects.get(pk=community_id)
        return CommunityDetailSchema.from_orm(community)
    except ObjectDoesNotExist:
        raise Http404(f"Community with ID {community_id} not found.")
    except ValueError:
        return {"error": "Invalid community ID format."}, 400
    except Exception as e:
        return {"error": str(e)}, 500


@router.get("/slug/{slug}/", response=CommunityDetailSchema)
def get_community_by_slug(request, slug: str):
    try:
        # Fetch community by slug
        community = Community.objects.get(slug=slug)
        return CommunityDetailSchema.from_orm(community)
    except ObjectDoesNotExist:
        raise Http404(f"Community with slug '{slug}' not found.")
    except Exception as e:
        return {"error": str(e)}, 500


@router.post("/", response=CommunitySchema, auth=JWTAuth())
def create_community(request: HttpRequest, payload: CreateCommunitySchema):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth
        # Validate the provided data and create a new Community
        new_community = Community(
            name=payload.name, description=payload.description, type=payload.type
        )
        new_community.full_clean()  # Validate fields
        new_community.save()

        new_community.admins.add(user)  # Add the creator as an admin

        return CommunitySchema.from_orm(new_community)

    except ValidationError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        return {"error": str(e)}, 500


@router.put("/{community_id}/", response=CommunitySchema, auth=JWTAuth())
@router.patch("/{community_id}/", response=CommunitySchema, auth=JWTAuth())
def update_community(
    request: HttpRequest, community_id: int, payload: UpdateCommunitySchema
):
    try:
        # Retrieve the authenticated user via request.auth
        user = request.auth

        # Retrieve the community by ID
        community = Community.objects.get(id=community_id)

        # Check if the user is an admin of this community
        if not community.admins.filter(id=user.id).exists():
            raise PermissionDenied(
                "You do not have permission to modify this community."
            )

        # Update the fields if provided in the payload
        if payload.name:
            community.name = payload.name
        if payload.description:
            community.description = payload.description
        if payload.type:
            community.type = payload.type

        # Validate and save changes
        community.full_clean()
        community.save()

        return CommunitySchema.from_orm(community)

    except ObjectDoesNotExist:
        return {"error": f"Community with ID {community_id} not found."}, 404
    except ValidationError as e:
        return {"error": str(e)}, 400
    except PermissionDenied as e:
        return {"error": str(e)}, 403
    except Exception as e:
        return {"error": str(e)}, 500


@router.delete("/{community_id}/", response={204: None}, auth=JWTAuth())
def delete_community(request: HttpRequest, community_id: int):
    try:
        # Retrieve the authenticated user via request.auth
        user = request.auth

        # Retrieve the specific community by ID
        community = Community.objects.get(id=community_id)

        # Check if the user is an admin of this community
        if not community.admins.filter(id=user.id).exists():
            raise PermissionDenied(
                "You do not have permission to delete this community."
            )

        # Delete the community
        community.delete()

        # Return a 204 (No Content) status to indicate successful deletion
        return None, 204

    except ObjectDoesNotExist:
        return {"error": f"Community with ID {community_id} not found."}, 404
    except PermissionDenied as e:
        return {"error": str(e)}, 403
    except Exception as e:
        return {"error": str(e)}, 500


"""
Membership Management Endpoints
"""


@router.post("/{community_id}/join-request/", response={201: str, 400: str, 404: str})
def create_join_request(request, community_id: int):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth

        # Retrieve the community
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            raise HttpError(404, f"Community with ID {community_id} does not exist.")

        # Check if the user is already a member
        if community.members.filter(id=user.id).exists():
            raise HttpError(400, "User is already a member of this community.")

        # Check for a pending or approved join request
        existing_request = (
            JoinRequest.objects.filter(user=user, community=community)
            .order_by("-requested_at")
            .first()
        )
        if existing_request:
            if existing_request.status in [JoinRequest.PENDING, JoinRequest.APPROVED]:
                raise HttpError(400, "A join request already exists for this user.")
            elif existing_request.status == JoinRequest.REJECTED:
                # Calculate the time elapsed since the rejection
                elapsed_time = timezone.now() - existing_request.rejection_timestamp
                if elapsed_time < timedelta(days=2):
                    raise HttpError(
                        400,
                        f"You can submit a new join request in "
                        f"{2 - elapsed_time.days} days.",
                    )

        # Create a new join request with a pending status
        JoinRequest.objects.create(
            user=user, community=community, status=JoinRequest.PENDING
        )
        return 201, "Join request submitted successfully."

    except HttpError as he:
        return he.status_code, str(he)
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.patch(
    "/{community_id}/requests/{request_id}/approve/",
    response={200: str, 403: str, 404: str},
)
def approve_join_request(request, community_id: int, request_id: int):
    user = request.auth  # Authenticated user retrieved via JWTAuth

    try:
        # Retrieve the community and the join request
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            raise HttpError(404, f"Community with ID {community_id} does not exist.")

        try:
            join_request = JoinRequest.objects.get(id=request_id, community=community)
        except JoinRequest.DoesNotExist:
            raise HttpError(
                404, f"Join request with ID {request_id} not found in this community."
            )

        # Check if the user is an admin or moderator in the community
        if (
            user not in community.admins.all()
            and user not in community.moderators.all()
        ):
            raise HttpError(
                403,
                "You do not have permission to approve \
                    join requests for this community.",
            )

        # Check if the join request is already approved or rejected
        if join_request.status != JoinRequest.PENDING:
            raise HttpError(400, "Only pending join requests can be approved.")

        # Approve the join request
        join_request.status = JoinRequest.APPROVED
        join_request.save()

        # Create a new membership for the user in the community
        Membership.objects.create(user=join_request.user, community=community)

        return 200, "Join request approved successfully."

    except HttpError as he:
        return he.status_code, str(he)
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.patch(
    "/{community_id}/requests/{request_id}/reject/",
    response={200: str, 403: str, 404: str},
)
def reject_join_request(request, community_id: int, request_id: int):
    user = request.auth  # Authenticated user retrieved via JWTAuth

    try:
        # Retrieve the community and the join request
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            raise HttpError(404, f"Community with ID {community_id} does not exist.")

        try:
            join_request = JoinRequest.objects.get(id=request_id, community=community)
        except JoinRequest.DoesNotExist:
            raise HttpError(
                404, f"Join request with ID {request_id} not found in this community."
            )

        # Check if the user is an admin or moderator in the community
        if (
            user not in community.admins.all()
            and user not in community.moderators.all()
        ):
            raise HttpError(
                403,
                "You do not have permission to reject join requests \
                    for this community.",
            )

        # Check if the join request is already approved or rejected
        if join_request.status != JoinRequest.PENDING:
            raise HttpError(400, "Only pending join requests can be rejected.")

        # Reject the join request and set the rejection timestamp
        join_request.status = JoinRequest.REJECTED
        join_request.rejection_timestamp = timezone.now()
        join_request.save()

        return 200, "Join request rejected successfully."

    except HttpError as he:
        return he.status_code, str(he)
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.get(
    "/{community_id}/members/",
    response={200: list[CommunityMemberSchema], 403: str, 404: str},
)
def list_community_members(request: HttpRequest, community_id: int):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth

        # Retrieve the community
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            raise HttpError(404, f"Community with ID {community_id} does not exist.")

        # Verify the authenticated user is an admin of this community
        if not community.admins.filter(id=user.id).exists():
            raise HttpError(
                403, "You do not have permission to view members of this community."
            )

        # Retrieve all members of the community
        members = community.members.all()

        # Map members to a schema
        return [
            CommunityMemberSchema(
                id=member.id, username=member.username, email=member.email
            )
            for member in members
        ]

    except HttpError as he:
        return he.status_code, str(he)
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


@router.delete(
    "/{community_id}/members/{user_id}/", response={200: str, 403: str, 404: str}
)
def remove_member_from_community(request, community_id: int, user_id: int):
    try:
        # Retrieve the authenticated user from the JWT token
        user = request.auth

        # Retrieve the community
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            raise HttpError(404, f"Community with ID {community_id} does not exist.")

        # Verify the authenticated user is an admin of this community
        if not community.admins.filter(id=user.id).exists():
            raise HttpError(
                403, "You do not have permission to remove members from this community."
            )
        try:
            member_to_remove = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise HttpError(404, f"User with ID {user_id} does not exist.")

        # Check if the member is part of the community
        if not community.members.filter(id=member_to_remove.id).exists():
            raise HttpError(
                404, f"User with ID {user_id} is not a member of this community."
            )

        # Remove the user from the community members
        community.members.remove(member_to_remove)

        return (
            200,
            f"User {member_to_remove.username} successfully "
            f"removed from {community.name}.",
        )

    except HttpError as he:
        return he.status_code, str(he)
    except Exception as e:
        return 400, f"An unexpected error occurred: {str(e)}"


"""
Invitation Management Endpoints
"""


@router.post(
    "/communities/{community_id}/invite/", response={201: str, 400: str, 403: str}
)
def send_invitation(request, community_id: int, payload: InviteSchema):
    """
    Send an invitation to the specified user via email or username.
    Only community admins can invite new members.
    """
    # Check if the invitation is already sent to the user
    existing_invitation = Invitation.objects.filter(
        community_id=community_id, email=payload.email, username=payload.username
    ).first()

    if existing_invitation:
        return 400, "An invitation has already been sent to this user."

    # Fetch the community by ID
    community = get_object_or_404(Community, pk=community_id)

    # Verify if the authenticated user is an admin of the community
    if request.auth not in community.admins.all():
        raise HttpError(
            403, "You are not authorized to invite members to this community."
        )

    # Validate that either email or username is provided
    if not (payload.email or payload.username):
        raise HttpError(400, "You must provide either an email or a username.")

    # Check for the user's existence if a username is provided
    if payload.username:
        user = User.objects.filter(username=payload.username).first()
        if not user:
            return (
                400,
                "The specified user is not registered. Please request them to sign up.",
            )

    # Create a new invitation object
    invitation = Invitation(
        community=community,
        email=payload.email if payload.email else None,
        username=payload.username if payload.username else None,
        invited_at=timezone.now(),
    )
    invitation.save()

    # Use the signer's `sign` method to create an expiring token
    signed_token = signer.sign(invitation.id)

    link = f"{request.scheme}://{request.get_host()}/invitations/{signed_token}/accept/"

    # Send an email to the user with the invitation link
    send_mail(
        "Invitation to join a community",
        f"Please click on the link to accept the invitation: {link}",
        "test@gmail.com",
        [payload.email],
        fail_silently=False,
    )

    response_message = f"Invitation sent with token {signed_token}"

    return 201, response_message


@router.post("/invitations/{signed_token}/accept/", response={200: str, 400: str})
def accept_invitation(request, signed_token: str):
    """
    Accepts the invitation by verifying the signed token and adds the user
    to the community through the Membership model.
    """
    try:
        # Verify the signed token and check expiration
        invitation_id = signer.unsign(signed_token, max_age=60 * 60 * 48)  # 48 hours
    except SignatureExpired:
        raise HttpError(
            400, "The invitation link has expired. Please request a new one."
        )
    except BadSignature:
        raise HttpError(400, "Invalid invitation token.")

    # Retrieve the invitation object
    invitation = get_object_or_404(Invitation, pk=invitation_id)

    # Check if the user is authenticated (assumes they are signed up)
    if not request.auth:
        raise HttpError(400, "You must be logged in to accept this invitation.")

    # Verify that the user isn't already a member of the community
    existing_membership = Membership.objects.filter(
        user=request.auth, community=invitation.community
    ).first()

    if existing_membership:
        return (
            200,
            f"You are already a member of the {invitation.community.name} community.",
        )

    # Create a new membership for the user in the community
    Membership.objects.create(user=request.auth, community=invitation.community)

    return (
        200,
        f"You have successfully joined the {invitation.community.name} community.",
    )
