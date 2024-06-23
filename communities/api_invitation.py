from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.validators import validate_email
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from communities.models import Community, Invitation, Membership
from communities.schemas import (
    CommunityInvitationDetails,
    InvitationDetails,
    InvitationResponseRequest,
    InvitePayload,
    Message,
    SendInvitationsPayload,
)
from users.auth import JWTAuth
from users.models import Notification, User

router = Router(tags=["Community Invitations"])


"""
Invitation Management Endpoints
"""


@router.post(
    "/communities/{community_id}/invite-users",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def invite_registered_users(request, community_id: int, payload: InvitePayload):
    try:
        community = Community.objects.get(pk=community_id)

        # Check if the requester is an admin of the community
        if request.auth not in community.admins.all():
            return 403, {"message": "Only community admins can send invitations."}

        # check for non-existing users
        existing_users = User.objects.filter(username__in=payload.usernames)
        if len(existing_users) != len(payload.usernames):
            nonexistent_users = set(payload.usernames) - set(
                user.username for user in existing_users
            )
            return 400, {
                "message": f"User(s) {', '.join(nonexistent_users)} do not exist."
            }

        # check for existing invitations
        existing_invitations = Invitation.objects.filter(
            community=community,
            username__in=payload.usernames,
            status=Invitation.PENDING,
        )

        if existing_invitations.exists():
            invited_usernames = [inv.username for inv in existing_invitations]
            return 400, {
                "message": f"Invitation(s) already exists for "
                f"{', '.join(invited_usernames)}."
            }

        # Send invitations
        for user in existing_users:
            invitation = Invitation.objects.create(
                community=community, username=user.username, status=Invitation.PENDING
            )
            link = (
                f"{settings.FRONTEND_URL}/community/{community_id}"
                f"/invitations/registered/{invitation.id}"
            )
            Notification.objects.create(
                user=user,
                message=f"You have been invited to join {community.name} community.",
                content=payload.note,
                link=link,
                category="communities",
                notification_type="join_request_received",
            )

        return 200, {"message": "Invitations sent successfully."}

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/invitations/{invitation_id}/respond",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def respond_to_invitation(
    request, invitation_id: int, payload: InvitationResponseRequest
):
    try:
        # Check if the invitation exists and the user has permission to respond to it
        invitation = Invitation.objects.get(
            pk=invitation_id, username=request.auth.username
        )

        # Check if the invitation has already been processed
        if invitation.status != Invitation.PENDING:
            return 400, {
                "message": f"Invitation is already "
                f"{invitation.get_status_display().lower()}."
            }

        if payload.action == "accept":
            invitation.status = Invitation.ACCEPTED
            Membership.objects.create(user=request.auth, community=invitation.community)
            response_message = (
                "Congratulations! You have successfully joined the community."
            )
        elif payload.action == "reject":
            invitation.status = Invitation.REJECTED
            response_message = "Invitation has been rejected successfully."

        invitation.save()

        # Optional: Send notification to community admin about the decision
        Notification.objects.create(
            user=invitation.community.admins.first(),
            message=f"{request.auth.username} has {payload.action}ed the "
            f"invitation to join {invitation.community.name}.",
            category="communities",
            notification_type="join_request_responded",
        )

        return 200, {"message": response_message}
    except Invitation.DoesNotExist:
        return 404, {
            "message": "Invitation does not exist or you "
            "do not have permission to respond to it."
        }
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/communities/{community_id}/send-invitations",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def send_invitations_to_unregistered_users(
    request, community_id: int, payload: SendInvitationsPayload
):
    try:
        community = Community.objects.get(pk=community_id)

        # Check if the requester is an admin of the community
        if request.auth not in community.admins.all():
            return 403, {"message": "Only community admins can send invitations."}

        # validate all emails
        valid_emails = []
        invalid_emails = []
        for email in payload.emails:
            try:
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            return 400, {"message": f"Invalid email(s): {', '.join(invalid_emails)}."}

        # Check for existing users
        existing_users = User.objects.filter(email__in=payload.emails)

        if existing_users.exists():
            existing_emails = [user.email for user in existing_users]
            return 400, {
                "message": f"User(s) with email(s) "
                f"{', '.join(existing_emails)} already exist."
            }

        # Check for existing invitations
        existing_invitations = Invitation.objects.filter(
            community=community,
            email__in=payload.emails,
            status=Invitation.PENDING,
        )

        if existing_invitations.exists():
            existing_emails = [inv.email for inv in existing_invitations]
            return 400, {
                "message": f"Invitation(s) already exists for "
                f"{', '.join(existing_emails)}."
            }

        # Send invitations
        signer = TimestampSigner()
        for email in valid_emails:
            try:
                signed_email = signer.sign(email)
                invitation = Invitation.objects.create(
                    community=community, email=email, status=Invitation.PENDING
                )
                message = (
                    f"{payload.body} \n Your referral link: "
                    f"{settings.FRONTEND_URL}/community/{community_id}/"
                    f"invitations/unregistered/{invitation.id}/{signed_email}"
                )
                send_mail(
                    subject=payload.subject,
                    message=message,
                    from_email="no-reply@example.com",
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception as e:
                return 500, {"message": str(e)}

        return 200, {"message": "Invitations sent successfully."}
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/invitations/respond/{token}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def respond_to_email_invitation(
    request, token: str, payload: InvitationResponseRequest
):
    signer = TimestampSigner()

    try:
        email = signer.unsign(token, max_age=345600)  # 4 days in seconds

        # Retrieve the invitation
        invitation = Invitation.objects.filter(
            email=email, status=Invitation.PENDING
        ).first()

        if not invitation:
            return 404, {
                "message": (
                    f"You have already "
                    f"{invitation.get_status_display().lower()} the invitation."
                )
            }

        # check whether the user has registered
        user = User.objects.filter(email=email).first()

        if not user:
            return 400, {
                "message": "Please register for an account and then click "
                "on the invitation link in your email to join the community."
            }

        if payload.action == "accept":
            invitation.status = Invitation.ACCEPTED
            Membership.objects.create(user=user, community=invitation.community)
            response_message = (
                "Invitation accepted and membership registered successfully."
            )
        elif payload.action == "reject":
            invitation.status = Invitation.REJECTED
            response_message = "Invitation rejected successfully."

        invitation.save()

        # Optional: Send notification to community admin about the decision
        Notification.objects.create(
            user=invitation.community.admins.first(),
            message=(
                f"{user.username} has {payload.action}ed the "
                f"invitation to join {invitation.community.name}."
            ),
            category="communities",
            notification_type="join_request_responded",
        )

        return {"message": response_message}

    except SignatureExpired:
        return 400, {"message": "Token expired."}
    except BadSignature:
        return 400, {"message": "Invalid token."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/{community_id}/invitations",
    auth=JWTAuth(),
    response={200: list[InvitationDetails], codes_4xx: Message, codes_5xx: Message},
)
def get_community_invitations(request, community_id: int):
    try:
        # Ensure the community exists
        community = Community.objects.get(pk=community_id)

        # Verify if the authenticated user is an admin of this community
        if request.auth not in community.admins.all():
            return 403, {"detail": "Only community admins can access the invitations."}

        # Fetch invitations related to the specified community
        invitations = Invitation.objects.filter(community=community).select_related(
            "community"
        )

        result = [
            {
                "id": invite.id,
                "email": invite.email,
                "username": invite.username,
                "invited_at": invite.invited_at.strftime("%Y-%m-%d %H:%M:%S"),
                "status": invite.get_status_display(),
            }
            for invite in invitations
        ]

        return result
    except Community.DoesNotExist:
        return 404, {"message": "Community not found"}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/{community_id}/invitation-details/{invitation_id}",
    response={200: CommunityInvitationDetails, codes_4xx: Message, codes_5xx: Message},
)
def get_community_invitation_details(request, community_id: int, invitation_id: int):
    try:
        community = Community.objects.get(pk=community_id)

        # Check if the invitation exists
        Invitation.objects.get(
            pk=invitation_id, community=community, status=Invitation.PENDING
        )

        return {
            "name": community.name,
            "description": community.description,
            "profile_pic_url": community.profile_pic_url,
            "num_members": community.members.count(),
        }
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Invitation.DoesNotExist:
        return 404, {
            "message": (
                "You have already responded to this invitation or it does not exist."
            )
        }
    except Exception as e:
        return 500, {"message": str(e)}
