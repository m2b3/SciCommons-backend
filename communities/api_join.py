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
        user = request.auth
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the user is an admin of the community
        if not community.admins.filter(id=user.id).exists():
            return 403, {
                "message": "You do not have administrative \
                        privileges in this community."
            }

        try:
            # Get all join requests for the community
            join_requests = JoinRequest.objects.filter(community=community)
            return 200, join_requests
        except Exception:
            return 500, {"message": "Error retrieving join requests. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/{community_id}/join",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def join_community(request, community_id: int):
    try:
        user = request.auth
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        try:
            # Check if the user is already a member
            if community.members.filter(id=user.id).exists():
                return 400, {"message": "You are already a member of this community."}
        except Exception:
            return 500, {"message": "Error checking community membership. Please try again."}

        try:
            # Check if there's already a pending join request
            if JoinRequest.objects.filter(user=user, community=community, status=JoinRequest.PENDING).exists():
                return 400, {"message": "You have already requested to join this community."}
        except Exception:
            return 500, {"message": "Error checking pending requests. Please try again."}

        # Process join request based on community settings
        try:
            if community.type == Community.PUBLIC and not community.requires_admin_approval:
                try:
                    community.members.add(user)
                except Exception:
                    return 500, {"message": "Error adding you to the community. Please try again."}
                return 200, {"message": "You have successfully joined the community."}

            # Create a join request
            try:
                JoinRequest.objects.create(user=user, community=community)
            except Exception:
                return 500, {"message": "Error creating join request. Please try again."}

            # Send a notification to the first admin
            try:
                Notification.objects.create(
                    user=community.admins.first(),
                    community=community,
                    notification_type="join_request_received",
                    message=f"New join request from {user.username}",
                    link=f"/community/{community.name}/requests",
                )
            except Exception:
                # Continue even if notification fails
                pass

            return 200, {"message": "Your request to join the community has been sent."}
        except Exception:
            return 500, {"message": "Error processing join request. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


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
        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception:
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the user is an admin of the community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {"message": "You do not have administrative privileges."}

        try:
            join_request = JoinRequest.objects.get(id=join_request_id, community=community)
        except JoinRequest.DoesNotExist:
            return 404, {"message": "Join request not found."}
        except Exception:
            return 500, {"message": "Error retrieving join request. Please try again."}

        if action not in ["approve", "reject"]:
            return 400, {"message": "Invalid action. Must be either 'approve' or 'reject'."}

        try:
            if action == "approve":
                join_request.status = JoinRequest.APPROVED
                try:
                    join_request.save()
                except Exception:
                    return 500, {"message": "Error updating join request status. Please try again."}
                
                try:
                    community.members.add(join_request.user)
                except Exception:
                    return 500, {"message": "Error adding user to community. Please try again."}

                # Send a notification to the user
                try:
                    Notification.objects.create(
                        user=join_request.user,
                        community=community,
                        notification_type="join_request_approved",
                        message=f"Your join request to {community.name} has been approved.",
                        link=f"/community/{community.name}",
                    )
                except Exception:
                    # Continue even if notification fails
                    pass

                return 200, {
                    "message": f"Join request approved. \
                            {join_request.user.username} is now a member of the community."
                }

            elif action == "reject":
                try:
                    join_request.status = JoinRequest.REJECTED
                    join_request.rejection_timestamp = timezone.now()
                    join_request.save()
                except Exception:
                    return 500, {"message": "Error updating join request status. Please try again."}
                
                return 200, {"message": "You have rejected the join request successfully."}
        except Exception:
            return 500, {"message": "Error processing join request action. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}
