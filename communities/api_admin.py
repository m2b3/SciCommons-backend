from typing import Literal

from django.db import transaction
from django.db.models import Q
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from communities.models import Community, Membership
from communities.schemas import (
    AdminArticlesResponse,
    MembersResponse,
    Message,
    UserSchema,
)
from users.auth import JWTAuth
from users.models import Notification

router = Router(auth=JWTAuth(), tags=["Community Admin"])

# Todo: Create a decorator function to check if the user is an admin of the community


@router.get(
    "/{community_name}/admin-articles",
    response={
        200: AdminArticlesResponse,
        codes_4xx: Message,
        codes_5xx: Message,
    },
)
def get_articles_by_status(request, community_name: str):
    try:
        # Check if the community exists
        community = Community.objects.get(name=community_name)

        # Check if the user is an admin of the community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {"message": "You do not have administrative privileges."}

        # Categorize articles by their publication status
        articles = {
            "published": [],
            "unpublished": [],
            "submitted": [],
            "community_id": community.id,
        }

        for article in Article.objects.filter(community=community):
            if article.published:
                articles["published"].append(article)
            elif article.status == "Approved" and not article.published:
                articles["unpublished"].append(article)
            elif article.status == "Pending":
                articles["submitted"].append(article)

        return 200, articles
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/{community_id}/manage-article/{article_id}/{action}",
    # url_name="manage_article",
    summary="Manage an article",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def manage_article(
    request,
    community_id: int,
    article_id: int,
    action: Literal["approve", "publish", "reject", "unpublish", "remove"],
):
    try:
        # Validate the action
        if action not in ["approve", "publish", "reject", "unpublish", "remove"]:
            return 400, {"message": "Invalid action."}

        community = Community.objects.get(id=community_id)

        # check if the user is an admin of the community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have administrative "
                "privileges in this community."
            }

        # Check if the article exists
        article = Article.objects.get(id=article_id)

        if not article.community:
            return 400, {"message": "Article is not submitted to any community."}

        # Check if the article belongs to the community
        if article.community != community:
            return 400, {"message": "Article does not belong to this community."}

        # Process the action
        if action == "approve":
            if article.status != "Pending":
                return 400, {
                    "message": "Only articles in 'Pending' status can be approved."
                }
            article.status = "Approved"
            article.save()
            # Send a notification to the author
            Notification.objects.create(
                user=article.submitter,
                article=article,
                community=community,
                category="articles",
                notification_type="article_approved",
                message=f"Your article '{article.title}' has been approved.",
                link=f"/community/{community.name}/{article.slug}",
                content=article.title,
            )

            return {"message": "Article approved successfully."}

        elif action == "reject":
            if article.status != "Pending":
                return 400, {
                    "message": "Only articles in 'Pending' status can be rejected."
                }
            article.status = "Rejected"
            article.save()
            # Send a notification to the author
            Notification.objects.create(
                user=article.submitter,
                community=community,
                article=article,
                category="articles",
                notification_type="article_rejected",
                message=f"Your article '{article.title}' has been rejected.",
                link=f"/community/{community.id}/{article.id}",
                content=article.title,
            )

            return 400, {"message": "Article rejected successfully."}

        elif action == "publish":
            if article.status != "Approved":
                return 400, {
                    "message": "Only approved articles can be published.  \
                        Please approve the article first."
                }
            article.published = True
            article.save()
            return {"message": "Article published successfully."}

        elif action == "unpublish":
            if not article.published:
                return 400, {"message": "Article is not published."}
            article.published = False
            article.save()
            return {"message": "Article unpublished successfully."}
        elif action == "remove":
            # remove from the community
            article.community = None
            article.status = "Pending"
            article.published = False
            article.save()

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/{community_name}/members",
    response={200: MembersResponse, codes_4xx: Message, codes_5xx: Message},
)
def get_community_members(request, community_name: str):
    try:
        community = Community.objects.get(name=community_name)

        # Check if the user is an admin of the community
        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have administrative \
                    privileges in this community."
            }

        def get_user_data(user):
            membership = Membership.objects.filter(
                user=user, community=community
            ).first()
            articles_published = Article.objects.filter(
                submitter=user, community=community, published=True
            ).count()
            return UserSchema(
                id=user.id,
                username=user.username,
                email=user.email,
                joined_at=membership.joined_at if membership else None,
                articles_published=articles_published,
            )

        # Get lists of distinct user groups
        moderators = set(community.moderators.all())
        reviewers = set(community.reviewers.all())
        admins = set(community.admins.all())

        # Exclude moderators, reviewers, and admins from members
        members = community.members.exclude(
            Q(id__in=[user.id for user in moderators])
            | Q(id__in=[user.id for user in reviewers])
            | Q(id__in=[user.id for user in admins])
        )

        members_data = [get_user_data(user) for user in members]
        moderators_data = [get_user_data(user) for user in moderators]
        reviewers_data = [get_user_data(user) for user in reviewers]
        admins_data = [get_user_data(user) for user in admins]

        return {
            "community_id": community.id,
            "members": members_data,
            "moderators": moderators_data,
            "reviewers": reviewers_data,
            "admins": admins_data,
        }
    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}


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
        "demote_admin": ("admins", "remove", "User demoted from admin successfully."),
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

        if not community.admins.filter(id=request.auth.id).exists():
            return 403, {
                "message": "You do not have administrative  \
                    privileges in this community."
            }

        user = community.members.get(id=user_id)
        role_group, method, success_message = role_actions[action]

        with transaction.atomic():
            getattr(getattr(community, role_group), method)(user)

        return 200, {"message": success_message}

    except Community.DoesNotExist:
        return 404, {"message": "Community not found."}
    except Exception as e:
        return 500, {"message": str(e)}
