import logging
from typing import Literal

from django.db import transaction
from django.db.models import Q
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from communities.models import Community, CommunityArticle, Membership
from communities.schemas import MembersResponse, Message, UserSchema
from users.auth import JWTAuth
from users.models import User

router = Router(auth=JWTAuth(), tags=["Community Members"])

# Module-level logger
logger = logging.getLogger(__name__)

# Todo: Create a decorator function to check if the user is an admin of the community


@router.get(
    "/{community_name}/members",
    response={200: MembersResponse, codes_4xx: Message, codes_5xx: Message},
)
def get_community_members(request, community_name: str):
    try:
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        # Check if the user is an admin of the community
        try:
            if not community.admins.filter(id=request.auth.id).exists():
                return 403, {
                    "message": "You do not have administrative \
                            privileges in this community."
                }
        except Exception as e:
            logger.error(f"Error checking administrative privileges: {e}")
            return 500, {
                "message": "Error checking administrative privileges. Please try again."
            }

        def get_user_data(user: User):
            try:
                membership = Membership.objects.filter(
                    user=user, community=community
                ).first()

                # Fetch submitted articles
                articles_submitted = CommunityArticle.objects.filter(
                    article__submitter=user, community=community
                ).count()

                # Fetch published articles
                articles_published = CommunityArticle.objects.filter(
                    article__submitter=user,
                    community=community,
                    status=CommunityArticle.PUBLISHED,
                ).count()

                # Fetch reviewed articles
                articles_reviewed = (
                    CommunityArticle.objects.filter(
                        assigned_reviewers=user, community=community
                    )
                    .exclude(status=CommunityArticle.SUBMITTED)
                    .count()
                )

                return UserSchema(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    profile_pic_url=user.profile_pic_url,
                    joined_at=membership.joined_at if membership else None,
                    articles_submitted=articles_submitted,
                    articles_published=articles_published,
                    articles_reviewed=articles_reviewed,
                )
            except Exception:
                # If there's an error processing a user, return a minimal record instead of failing
                return UserSchema(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    profile_pic_url=user.profile_pic_url,
                    joined_at=None,
                    articles_submitted=0,
                    articles_published=0,
                    articles_reviewed=0,
                )

        try:
            # Get lists of distinct user groups
            moderators = set(community.moderators.all())
            reviewers = set(community.reviewers.all())
            admins = set(community.admins.all())
        except Exception as e:
            logger.error(f"Error retrieving community roles: {e}")
            return 500, {
                "message": "Error retrieving community roles. Please try again."
            }

        try:
            # Exclude moderators, reviewers, and admins from members
            members = community.members.exclude(
                Q(id__in=[user.id for user in moderators])
                | Q(id__in=[user.id for user in reviewers])
                | Q(id__in=[user.id for user in admins])
            )
        except Exception as e:
            logger.error(f"Error filtering community members: {e}")
            return 500, {
                "message": "Error filtering community members. Please try again."
            }

        try:
            members_data = [get_user_data(user) for user in members]
            moderators_data = [get_user_data(user) for user in moderators]
            reviewers_data = [get_user_data(user) for user in reviewers]
            admins_data = [get_user_data(user) for user in admins]
        except Exception as e:
            logger.error(f"Error processing member data: {e}")
            return 500, {"message": "Error processing member data. Please try again."}

        return 200, {
            "community_id": community.id,
            "members": members_data,
            "moderators": moderators_data,
            "reviewers": reviewers_data,
            "admins": admins_data,
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/{community_id}/manage-member/{user_id}/{action}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def manage_community_member(
    request,
    community_id: int,
    user_id: int,
    action: Literal[
        "promote_admin",
        "promote_moderator",
        "promote_reviewer",
        "demote_admin",
        "demote_moderator",
        "demote_reviewer",
        "remove",
    ],
):
    try:
        role_actions = {
            "promote_admin": ("admins", "add", "User promoted to admin successfully."),
            "promote_moderator": (
                "moderators",
                "add",
                "User promoted to moderator successfully.",
            ),
            "promote_reviewer": (
                "reviewers",
                "add",
                "User promoted to reviewer successfully.",
            ),
            "demote_admin": (
                "admins",
                "remove",
                "User demoted from admin successfully.",
            ),
            "demote_moderator": (
                "moderators",
                "remove",
                "User demoted from moderator successfully.",
            ),
            "demote_reviewer": (
                "reviewers",
                "remove",
                "User demoted from reviewer successfully.",
            ),
            "remove": (
                "members",
                "remove",
                "User removed from the community successfully.",
            ),
        }

        if action not in role_actions:
            return 400, {"message": "Invalid action."}

        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return 404, {"message": "Community not found."}
        except Exception as e:
            logger.error(f"Error retrieving community: {e}")
            return 500, {"message": "Error retrieving community. Please try again."}

        try:
            if not community.admins.filter(id=request.auth.id).exists():
                return 403, {
                    "message": "You do not have administrative  \
                        privileges in this community."
                }
        except Exception as e:
            logger.error(f"Error checking administrative privileges: {e}")
            return 500, {
                "message": "Error checking administrative privileges. Please try again."
            }

        try:
            user = community.members.get(id=user_id)
        except User.DoesNotExist:
            return 404, {"message": "User not found in this community."}
        except Exception as e:
            logger.error(f"Error retrieving user: {e}")
            return 500, {"message": "Error retrieving user. Please try again."}

        role_group, method, success_message = role_actions[action]

        try:
            with transaction.atomic():
                try:
                    getattr(getattr(community, role_group), method)(user)
                except Exception as e:
                    logger.error(f"Error updating user's role: {e}")
                    return 500, {
                        "message": f"Error updating user's role. Please try again."
                    }
        except Exception as e:
            logger.error(f"Error during transaction: {e}")
            return 500, {"message": "Error during transaction. Please try again."}

        return 200, {"message": success_message}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
