import logging

from django.conf import settings
from django.core.exceptions import ValidationError
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
from myapp.services.send_emails import send_email_task
from users.auth import JWTAuth
from users.models import Notification, User

router = Router(tags=["Community Invitations"])

# Module-level logger
logger = logging.getLogger(__name__)


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
        try:
            community = Community.objects.get(pk=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the requester is an admin of the community
        if request.auth not in community.admins.all():
            return 403, {"message": "Only community admins can send invitations."}

        try:
            # check for non-existing users
            existing_users = User.objects.filter(username__in=payload.usernames)
            if len(existing_users) != len(payload.usernames):
                nonexistent_users = set(payload.usernames) - set(
                    user.username for user in existing_users
                )
                return 400, {
                    "message": f"User(s) {', '.join(nonexistent_users)} do not exist."
                }
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return 500, {"message": "Error checking user existence. Please try again."}

        try:
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
        except Exception as e:
            logger.error(f"Error checking existing invitations: {e}")
            return 500, {
                "message": "Error checking existing invitations. Please try again."
            }

        # Send invitations
        try:
            for user in existing_users:
                try:
                    invitation = Invitation.objects.create(
                        community=community,
                        username=user.username,
                        status=Invitation.PENDING,
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
                except Exception as e:
                    logger.error(f"Error creating invitation for user: {e}")
                    return 500, {
                        "message": "Error creating invitation for user. Please try again."
                    }
        except Exception as e:
            logger.error(f"Error sending invitations: {e}")
            return 500, {"message": "Error sending invitations. Please try again."}

        return 200, {"message": "Invitations sent successfully."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/invitations/{invitation_id}/respond",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def respond_to_invitation(
    request, invitation_id: int, payload: InvitationResponseRequest
):
    try:
        try:
            # Check if the invitation exists and the user has permission to respond to it
            invitation = Invitation.objects.get(
                pk=invitation_id, username=request.auth.username
            )
        except Invitation.DoesNotExist:
            return 404, {
                "message": "Invitation does not exist or you "
                "do not have permission to respond to it."
            }
        except Exception as e:
            logger.error(f"Error retrieving invitation: {e}")
            return 500, {"message": "Error retrieving invitation. Please try again."}

        # Check if the invitation has already been processed
        if invitation.status != Invitation.PENDING:
            return 400, {
                "message": f"Invitation is already "
                f"{invitation.get_status_display().lower()}."
            }

        try:
            if payload.action == "accept":
                invitation.status = Invitation.ACCEPTED
                try:
                    Membership.objects.create(
                        user=request.auth, community=invitation.community
                    )
                except Exception as e:
                    logger.error(f"Error creating membership: {e}")
                    return 500, {
                        "message": "Error creating membership. Please try again."
                    }
                response_message = (
                    "Congratulations! You have successfully joined the community."
                )
            elif payload.action == "reject":
                invitation.status = Invitation.REJECTED
                response_message = "Invitation has been rejected successfully."
            else:
                return 400, {
                    "message": "Invalid action. Please specify 'accept' or 'reject'."
                }

            try:
                invitation.save()
            except Exception as e:
                logger.error(f"Error updating invitation status: {e}")
                return 500, {
                    "message": "Error updating invitation status. Please try again."
                }
        except Exception as e:
            logger.error(f"Error processing your response: {e}")
            return 500, {"message": "Error processing your response. Please try again."}

        # Optional: Send notification to community admin about the decision
        try:
            Notification.objects.create(
                user=invitation.community.admins.first(),
                message=f"{request.auth.username} has {payload.action}ed the "
                f"invitation to join {invitation.community.name}.",
                category="communities",
                notification_type="join_request_responded",
            )
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            # Continue even if notification fails - the invitation was already processed
            pass

        return 200, {"message": response_message}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/communities/{community_id}/send-invitations",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def send_invitations_to_unregistered_users(
    request, community_id: int, payload: SendInvitationsPayload
):
    try:
        try:
            community = Community.objects.get(pk=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the requester is an admin of the community
        if request.auth not in community.admins.all():
            return 403, {"message": "Only community admins can send invitations."}

        # validate all emails
        try:
            valid_emails = []
            invalid_emails = []
            for email in payload.emails:
                try:
                    validate_email(email)
                    valid_emails.append(email)
                except ValidationError:
                    invalid_emails.append(email)

            if invalid_emails:
                return 400, {
                    "message": f"Invalid email(s): {', '.join(invalid_emails)}."
                }
        except Exception as e:
            logger.error(f"Error validating email addresses: {e}")
            return 500, {
                "message": "Error validating email addresses. Please try again."
            }

        # Check for existing users
        # existing_users = User.objects.filter(email__in=payload.emails)

        # if existing_users.exists():
        #     existing_emails = [user.email for user in existing_users]
        #     return 400, {
        #         "message": f"User(s) with email(s) "
        #         f"{', '.join(existing_emails)} already exist."
        #     }

        # Check for existing invitations
        try:
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
        except Exception as e:
            logger.error(f"Error checking existing invitations: {e}")
            return 500, {
                "message": "Error checking existing invitations. Please try again."
            }

        # Send invitations
        try:
            signer = TimestampSigner()
            template_context = {
                "community_name": community.name,
                "community_members": community.members.count(),
            }

            for email in valid_emails:
                try:
                    signed_email = signer.sign(email)
                    invitation = Invitation.objects.create(
                        community=community, email=email, status=Invitation.PENDING
                    )
                    template_context["referral_link"] = (
                        f"{settings.FRONTEND_URL}/community/{community_id}/invitations/unregistered/{invitation.id}/{signed_email}"
                    )
                    # message = (
                    #     f"{payload.body} \n Your referral link: "
                    #     f"{settings.FRONTEND_URL}/community/{community_id}/"
                    #     f"invitations/unregistered/{invitation.id}/{signed_email}"
                    # )
                    # send_email_task.delay(
                    #     subject=payload.subject,
                    #     message=message,
                    #     recipient_list=[email],
                    #     is_html=False,
                    # )
                    send_email_task.delay(
                        subject=payload.subject,
                        html_template_name="community_invitation_template.html",
                        context=template_context,
                        recipient_list=[email],
                    )
                except Exception as e:
                    logger.error(f"Error sending invitation to {email}: {e}")
                    return 500, {
                        "message": f"Error sending invitation to {email}. Please try again."
                    }
        except Exception as e:
            logger.error(f"Error sending invitations: {e}")
            return 500, {"message": "Error sending invitations. Please try again."}

        return 200, {"message": "Invitations sent successfully."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/invitations/respond/{token}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def respond_to_email_invitation(
    request, token: str, payload: InvitationResponseRequest
):
    try:
        signer = TimestampSigner()

        try:
            email = signer.unsign(token, max_age=345600)  # 4 days in seconds
        except SignatureExpired:
            return 400, {"message": "Token expired. Please request a new invitation."}
        except BadSignature:
            return 400, {"message": "Invalid token. Please check the invitation link."}
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return 500, {"message": "Error verifying token. Please try again."}

        try:
            # Retrieve the invitation
            invitation = Invitation.objects.filter(
                email=email, status=Invitation.PENDING
            ).first()

            if not invitation:
                processed_invitation = (
                    Invitation.objects.filter(email=email)
                    .exclude(status=Invitation.PENDING)
                    .first()
                )

                if processed_invitation:
                    return 400, {
                        "message": (
                            f"You have already "
                            f"{processed_invitation.get_status_display().lower()} the invitation."
                        )
                    }
                return 404, {"message": "Invitation not found."}
        except Exception as e:
            logger.error(f"Error retrieving invitation: {e}")
            return 500, {"message": "Error retrieving invitation. Please try again."}

        try:
            # check whether the user has registered
            user = User.objects.filter(email=email).first()

            if not user:
                return 400, {
                    "message": "Please register for an account and then click "
                    "on the invitation link in your email to join the community."
                }
        except Exception as e:
            logger.error(f"Error checking user status: {e}")
            return 500, {"message": "Error checking user status. Please try again."}

        try:
            if payload.action == "accept":
                try:
                    invitation.status = Invitation.ACCEPTED
                    Membership.objects.create(user=user, community=invitation.community)
                    response_message = (
                        "Invitation accepted and membership registered successfully."
                    )
                except Exception as e:
                    logger.error(f"Error creating membership: {e}")
                    return 500, {
                        "message": "Error creating membership. Please try again."
                    }
            elif payload.action == "reject":
                invitation.status = Invitation.REJECTED
                response_message = "Invitation rejected successfully."
            else:
                return 400, {
                    "message": "Invalid action. Please specify 'accept' or 'reject'."
                }

            try:
                invitation.save()
            except Exception as e:
                logger.error(f"Error updating invitation status: {e}")
                return 500, {
                    "message": "Error updating invitation status. Please try again."
                }
        except Exception as e:
            logger.error(f"Error processing your response: {e}")
            return 500, {"message": "Error processing your response. Please try again."}

        try:
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
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            # Continue even if notification fails - the invitation was already processed
            pass

        return 200, {"message": response_message}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{community_name}/invitations",
    auth=JWTAuth(),
    response={200: list[InvitationDetails], codes_4xx: Message, codes_5xx: Message},
)
def get_community_invitations(request, community_name: str):
    try:
        try:
            # Ensure the community exists
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        # Verify if the authenticated user is an admin of this community
        if request.auth not in community.admins.all():
            return 403, {"message": "Only community admins can access the invitations."}

        try:
            # Fetch invitations related to the specified community
            invitations = Invitation.objects.filter(community=community).select_related(
                "community"
            )
        except Exception as e:
            logger.error(f"Error retrieving invitations: {e}")
            return 500, {"message": "Error retrieving invitations. Please try again."}

        try:
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

            return 200, result
        except Exception as e:
            logger.error(f"Error formatting invitation data: {e}")
            return 500, {
                "message": "Error formatting invitation data. Please try again."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{community_id}/invitation-details/{invitation_id}",
    response={200: CommunityInvitationDetails, codes_4xx: Message, codes_5xx: Message},
)
def get_community_invitation_details(request, community_id: int, invitation_id: int):
    try:
        try:
            community = Community.objects.get(pk=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the invitation exists
        try:
            Invitation.objects.get(
                pk=invitation_id, community=community, status=Invitation.PENDING
            )
        except Invitation.DoesNotExist:
            return 404, {
                "message": (
                    "You have already responded to this invitation or it does not exist."
                )
            }
        except Exception as e:
            logger.error(f"Error retrieving invitation: {e}")
            return 500, {"message": "Error retrieving invitation. Please try again."}

        try:
            return 200, {
                "name": community.name,
                "description": community.description,
                # "profile_pic_url": community.profile_pic_url,
                "num_members": community.members.count(),
            }
        except Exception as e:
            logger.error(f"Error formatting community data: {e}")
            return 500, {
                "message": "Error formatting community data. Please try again."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
