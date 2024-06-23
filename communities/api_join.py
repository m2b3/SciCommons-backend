from typing import List, Literal

from django.utils import timezone
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from communities.models import Community, JoinRequest
from communities.schemas import JoinRequestSchema, Message
from users.auth import JWTAuth
from users.models import Notification

router = Router(auth=JWTAuth(), tags=["Join Community"])


"""
Membership Management Endpoints
"""


@router.get(
    "/{community_name}/join-requests",
    response={200: List[JoinRequestSchema], codes_4xx: Message, codes_5xx: Message},
)
def get_join_requests(request, community_name: str):
    try:
        user = request.auth  # Assuming `request.auth` provides the user object
        community = Community.objects.get(name=community_name)

        # Check if the user is an admin of the community
        if not community.admins.filter(id=user.id).exists():
            return 403, {
                "message": "You do not have administrative \
                    privileges in this community."
            }

        # Get all join requests for the community
        join_requests = JoinRequest.objects.filter(community=community)

        return join_requests

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}

    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/{community_id}/join",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def join_community(request, community_id: int):
    try:
        user = request.auth
        community = Community.objects.get(id=community_id)

        # Check if the user is already a member
        if community.members.filter(id=user.id).exists():
            return 400, {"message": "You are already a member of this community."}

        if community.type == Community.PUBLIC:
            # Directly add the user to the community if it is public
            community.members.add(user)
            return {"message": "You have successfully joined the community."}

        elif community.type == Community.LOCKED:
            # Check if there's already a pending join request
            if JoinRequest.objects.filter(
                user=user, community=community, status=JoinRequest.PENDING
            ).exists():
                return 400, {
                    "message": "You have already requested to join this community."
                }

            # Create a join request if the community is locked
            JoinRequest.objects.create(user=user, community=community)

            # Send a notification to the admins
            Notification.objects.create(
                user=community.admins.first(),
                community=community,
                notification_type="join_request_received",
                message=f"New join request from {user.username}",
                link=f"/community/{community.name}/requests",
            )

            return {"message": "Your request to join the community has been sent."}
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/{community_id}/manage-join-request/{join_request_id}/{action}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def manage_join_request(
    request,
    community_id: int,
    join_request_id: int,
    action: Literal["approve", "reject"],
):
    try:
        community = Community.objects.get(id=community_id)

        # Check if the user is an admin of the community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {"message": "You do not have administrative privileges."}

        join_request = JoinRequest.objects.get(id=join_request_id, community=community)

        if action == "approve":
            join_request.status = JoinRequest.APPROVED
            join_request.save()
            community.members.add(join_request.user)

            # Send a notification to the user
            Notification.objects.create(
                user=join_request.user,
                community=community,
                notification_type="join_request_approved",
                message=f"Your join request to {community.name} has been approved.",
                link=f"/community/{community.name}",
            )

            return {
                "message": f"Join request approved. \
                    {join_request.user.username} is now a member of the community."
            }

        elif action == "reject":
            join_request.status = JoinRequest.REJECTED
            join_request.rejection_timestamp = timezone.now()
            join_request.save()
            return {"message": "You have rejected the join request successfully."}

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except JoinRequest.DoesNotExist:
        return 404, {"message": "Join request not found."}
    except Exception as e:
        return 500, {"message": str(e)}
