import logging
from typing import List, Optional

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import (
    AnonymousIdentity,
    Article,
    Discussion,
    DiscussionComment,
    DiscussionSubscription,
    DiscussionSummary,
    Reaction,
)
from articles.schemas import (
    CommunitySubscriptionOut,
    CreateDiscussionSchema,
    DiscussionCommentCreateSchema,
    DiscussionCommentOut,
    DiscussionCommentUpdateSchema,
    DiscussionOut,
    DiscussionSubscriptionOut,
    DiscussionSubscriptionSchema,
    DiscussionSubscriptionUpdateSchema,
    DiscussionSummaryCreateSchema,
    DiscussionSummaryOut,
    DiscussionSummaryUpdateSchema,
    PaginatedDiscussionSchema,
    SubscriptionStatusSchema,
    UserSubscriptionsOut,
)
from communities.models import Community, CommunityArticle
from myapp.realtime import RealtimeEventPublisher
from myapp.schemas import Message, UserStats
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Reputation, User

router = Router(tags=["Discussions"])
logger = logging.getLogger(__name__)

"""
Article discussions API
"""


@router.post(
    "/{article_id}/discussions/",
    response={201: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_discussion(
    request,
    article_id: int,
    discussion_data: CreateDiscussionSchema,
    community_id: Optional[int] = None,
):
    try:
        with transaction.atomic():
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return 404, {"message": "Article not found."}
            except Exception as e:
                logger.error(f"Error retrieving article: {e}")
                return 500, {"message": "Error retrieving article. Please try again."}

            user = request.auth

            community = None
            is_pseudonymous = False
            if community_id:
                try:
                    community = Community.objects.get(id=community_id)
                except Community.DoesNotExist:
                    return 404, {"message": "Community not found."}
                except Exception as e:
                    logger.error(f"Error retrieving community: {e}")
                    return 500, {
                        "message": "Error retrieving community. Please try again."
                    }

                if not community.is_member(user):
                    return 403, {"message": "You are not a member of this community."}

                try:
                    community_article = CommunityArticle.objects.get(
                        article=article, community=community
                    )
                    if community_article.is_pseudonymous:
                        is_pseudonymous = True
                except CommunityArticle.DoesNotExist:
                    return 404, {"message": "Article not found in this community."}
                except Exception as e:
                    logger.error(f"Error retrieving community article: {e}")
                    return 500, {
                        "message": "Error retrieving community article. Please try again."
                    }

            try:
                discussion = Discussion.objects.create(
                    article=article,
                    author=user,
                    community=community,
                    topic=discussion_data.topic,
                    content=discussion_data.content,
                    is_pseudonymous=is_pseudonymous,
                )
            except Exception as e:
                logger.error(f"Error creating discussion: {e}")
                return 500, {"message": "Error creating discussion. Please try again."}

            if is_pseudonymous:
                try:
                    # Create an anonymous name for the user who created the review
                    discussion.get_anonymous_name()
                except Exception:
                    logger.error(
                        "Error creating anonymous name for discussion", exc_info=True
                    )
                    # Continue even if anonymous name creation fails

            # Publish real-time event for private communities only
            try:
                if discussion.community and discussion.community.type == "private":
                    community_ids = {discussion.community.id}
                    RealtimeEventPublisher.publish_discussion_created(
                        discussion, community_ids
                    )
            except Exception as e:
                logger.error(f"Failed to publish discussion created event: {e}")
                # Continue even if event publishing fails

        try:
            return 201, DiscussionOut.from_orm(discussion, user)
        except Exception as e:
            logger.error(f"Error formatting discussion data: {e}")
            return 500, {
                "message": "Discussion created but error retrieving discussion data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{article_id}/discussions/",
    response={200: PaginatedDiscussionSchema, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_discussions(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    try:
        try:
            # article = Article.objects.get(id=article_id)
            article = Article.objects.only("id").get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        community = None
        if community_id:
            try:
                community = Community.objects.only("id", "type").get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            if not community.is_member(request.auth) and community.type == "hidden":
                return 403, {"message": "You are not a member of this community."}

        # Filter discussions and annotate with comments count
        discussions = (
            Discussion.objects.filter(article=article, community=community)
            .select_related("author", "article", "community")
            # Use the correct related_name "discussion_comments" configured on
            # the DiscussionComment model.
            .annotate(comments_count=Count("discussion_comments"))
            .order_by("-created_at")
        )

        try:
            paginator = Paginator(discussions, size)
            page_obj = paginator.page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        current_user: Optional[User] = None if not request.auth else request.auth

        try:
            discussions_list = list(page_obj.object_list)

            # Prefetch reputations in one query
            author_ids = set(d.author_id for d in discussions_list)
            reputations = {
                rep.user_id: rep
                for rep in Reputation.objects.filter(user_id__in=author_ids)
            }

            # Prefetch pseudonyms in one query (for only pseudonymous discussions)
            pseudonym_map = {}
            pseudonym_needed = [d for d in discussions_list if d.is_pseudonymous]
            if pseudonym_needed:
                pseudonyms = AnonymousIdentity.objects.filter(
                    article=article,
                    user_id__in=[d.author_id for d in pseudonym_needed],
                    community=community,
                )
                for p in pseudonyms:
                    pseudonym_map[(p.user_id, p.article_id, p.community_id)] = p

            current_user = request.auth if request.auth else None
            items = []
            for discussion in discussions_list:
                reputation = reputations.get(discussion.author_id)
                # Use basic user details and attach prefetched reputation to avoid
                # additional DB queries (UserStats.from_model doesn’t accept a
                # "reputation" kwarg).
                user = UserStats.from_model(
                    discussion.author,
                    basic_details=True,
                )

                if reputation:
                    user.reputation_score = reputation.score
                    user.reputation_level = reputation.level

                if discussion.is_pseudonymous:
                    key = (
                        discussion.author_id,
                        discussion.article_id,
                        community.id if community else None,
                    )
                    pseudonym = pseudonym_map.get(key)
                    if pseudonym:
                        user.username = pseudonym.fake_name
                        user.profile_pic_url = pseudonym.identicon

                items.append(
                    DiscussionOut(
                        id=discussion.id,
                        topic=discussion.topic,
                        content=discussion.content,
                        created_at=discussion.created_at,
                        updated_at=discussion.updated_at,
                        deleted_at=discussion.deleted_at,
                        user=user,
                        is_author=(discussion.author == current_user),
                        article_id=article.id,
                        comments_count=discussion.comments_count,
                        is_pseudonymous=discussion.is_pseudonymous,
                        is_resolved=discussion.is_resolved,
                    )
                )

            return 200, PaginatedDiscussionSchema(
                items=items,
                total=paginator.count,
                page=page,
                per_page=size,
            )
        except Exception as e:
            logger.error(f"Error formatting discussion data: {e}")
            return 500, {
                "message": "Error formatting discussion data. Please try again."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/my-subscriptions/",
    response={
        200: UserSubscriptionsOut,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def get_user_subscriptions(request):
    """
    Get all active subscriptions for the current user grouped by community
    """
    try:
        user = request.auth

        try:
            # Get all active subscriptions with related data
            subscriptions = (
                DiscussionSubscription.objects.filter(user=user, is_active=True)
                .select_related("community_article", "community", "article")
                .order_by("community__name", "-subscribed_at")
            )

            # Get community IDs to check admin status in bulk
            community_ids = set(s.community_id for s in subscriptions)

            # Bulk check which communities user is admin of
            admin_community_ids = set(
                Community.objects.filter(id__in=community_ids, admins=user).values_list(
                    "id", flat=True
                )
            )

            # Group subscriptions by community
            communities_dict = {}
            for subscription in subscriptions:
                community_id = subscription.community_id

                if community_id not in communities_dict:
                    communities_dict[community_id] = {
                        "community_id": community_id,
                        "community_name": subscription.community.name,
                        "is_admin": community_id in admin_community_ids,
                        "articles": [],
                    }

                # Add article info to the community
                communities_dict[community_id]["articles"].append(
                    {
                        "article_id": subscription.article_id,
                        "article_title": subscription.article.title,
                        "article_slug": subscription.article.slug,
                        "article_abstract": subscription.article.abstract,
                        "community_article_id": subscription.community_article_id,
                    }
                )

            # Convert dict to list of CommunitySubscriptionOut objects
            communities_list = [
                CommunitySubscriptionOut(**community_data)
                for community_data in communities_dict.values()
            ]

            return 200, UserSubscriptionsOut(communities=communities_list)

        except Exception as e:
            logger.error(f"Error retrieving user subscriptions: {e}", exc_info=True)
            return 500, {"message": "Error retrieving subscriptions. Please try again."}

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/subscription-status/",
    response={200: SubscriptionStatusSchema, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_subscription_status(request, community_article_id: int, community_id: int):
    """
    Check if user is subscribed to discussions for a specific community article
    """
    try:
        user = request.auth

        # Validate community article exists
        try:
            community_article = CommunityArticle.objects.select_related(
                "community", "article"
            ).get(id=community_article_id, community_id=community_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Community article not found."}
        except Exception as e:
            logger.error(f"Error retrieving community article: {e}")
            return 500, {
                "message": "Error retrieving community article. Please try again."
            }

        # Check if user is a member of the community
        if not community_article.community.is_member(user):
            return 403, {
                "message": "You must be a member of this community to check subscription status."
            }

        try:
            subscription = DiscussionSubscription.objects.get(
                user=user,
                community_article=community_article,
                community=community_article.community,
                is_active=True,
            )

            return 200, SubscriptionStatusSchema(
                is_subscribed=True,
                subscription=DiscussionSubscriptionOut.from_orm(subscription),
            )
        except DiscussionSubscription.DoesNotExist:
            return 200, SubscriptionStatusSchema(is_subscribed=False, subscription=None)
        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            return 500, {
                "message": "Error checking subscription status. Please try again."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/discussions/subscribe/",
    response={
        201: DiscussionSubscriptionOut,
        200: DiscussionSubscriptionOut,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def subscribe_to_discussion(request, subscription_data: DiscussionSubscriptionSchema):
    """
    Subscribe to discussions in a specific community article for real-time updates
    Only works for articles in private/hidden communities

    Args:
        subscription_data: Contains community_article_id and community_id
    """
    try:
        user = request.auth

        # Validate community article exists
        try:
            community_article = CommunityArticle.objects.select_related(
                "community", "article"
            ).get(id=subscription_data.community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Community article not found."}
        except Exception as e:
            logger.error(f"Error retrieving community article: {e}")
            return 500, {
                "message": "Error retrieving community article. Please try again."
            }

        # Validate community matches
        if community_article.community.id != subscription_data.community_id:
            return 400, {
                "message": "Community ID does not match the community article."
            }

        # Only allow subscriptions for private/hidden communities
        if community_article.community.type not in ["private", "hidden"]:
            return 400, {
                "message": "Subscriptions are only available for private and hidden communities."
            }

        # Check if user is a member of the community
        if not community_article.community.is_member(user):
            return 403, {
                "message": "You must be a member of this community to subscribe to discussions."
            }

        try:
            # Create or update subscription
            subscription, created = DiscussionSubscription.objects.update_or_create(
                user=user,
                community_article=community_article,
                community=community_article.community,
                defaults={
                    "article": community_article.article,
                    "is_active": True,
                },
            )
        except Exception as e:
            logger.error(f"Error creating/updating subscription: {e}")
            return 500, {"message": "Error creating subscription. Please try again."}

        status_code = 201 if created else 200
        action = "subscribed to" if created else "reactivated subscription for"

        logger.info(
            f"User {user.id} {action} discussions in community {community_article.community.id} for article {community_article.article.id}"
        )

        # Notify Tornado server about subscription change for immediate real-time updates
        try:
            from myapp.realtime import RealtimeQueueManager, get_user_community_ids

            community_ids = list(get_user_community_ids(user))
            RealtimeQueueManager.update_user_subscriptions(user.id, community_ids)
        except Exception as e:
            logger.warning(
                f"Failed to update real-time subscriptions for user {user.id}: {e}"
            )
            # Continue - real-time update failure shouldn't break subscription

        try:
            return status_code, DiscussionSubscriptionOut.from_orm(subscription)
        except Exception as e:
            logger.error(f"Error formatting subscription data: {e}")
            return 500, {
                "message": "Subscription created but error retrieving subscription data."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/{discussion_id}/",
    response={200: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_discussion(request, discussion_id: int):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            response_data = DiscussionOut.from_orm(discussion, user)
            return 200, response_data
        except Exception as e:
            logger.error(f"Error formatting discussion data: {e}")
            return 500, {
                "message": "Error formatting discussion data. Please try again."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/discussions/{discussion_id}/",
    response={201: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_discussion(
    request, discussion_id: int, discussion_data: CreateDiscussionSchema
):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth

        # Check if the review belongs to the user
        if discussion.author != user:
            return 403, {
                "message": "You do not have permission to update this discussion."
            }

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            # Update the review with new data if provided
            discussion.topic = discussion_data.topic or discussion.topic
            discussion.content = discussion_data.content or discussion.content
            discussion.save()
        except Exception as e:
            logger.error(f"Error updating discussion: {e}")
            return 500, {"message": "Error updating discussion. Please try again."}

        try:
            response_data = DiscussionOut.from_orm(discussion, user)
            return 201, response_data
        except Exception as e:
            logger.error(f"Error formatting discussion data: {e}")
            return 500, {
                "message": "Discussion updated but error retrieving discussion data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/{discussion_id}/",
    response={201: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_discussion(request, discussion_id: int):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        user = request.auth  # Assuming user is authenticated

        if discussion.author != user:
            return 403, {
                "message": "You do not have permission to delete this discussion."
            }

        if discussion.community and not discussion.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            discussion.topic = "[deleted]"
            discussion.content = "[deleted]"
            discussion.save()
        except Exception as e:
            logger.error(f"Error deleting discussion: {e}")
            return 500, {"message": "Error deleting discussion. Please try again."}

        return 201, {"message": "Discussion deleted successfully."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.patch(
    "/discussions/{discussion_id}/resolve/",
    response={200: DiscussionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def toggle_discussion_resolved(request, discussion_id: int):
    """
    Toggle the resolved status of a discussion.
    If resolved, it will be unresolved. If unresolved, it will be resolved.
    Only available for community articles and can only be done by:
    - Community admin
    - Discussion author

    Args:
        discussion_id: The ID of the discussion to toggle resolved status
    """
    try:
        user = request.auth

        try:
            discussion = Discussion.objects.select_related(
                "community", "article", "author"
            ).get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        # Check if this is a community discussion
        if not discussion.community:
            return 400, {
                "message": "Only discussions in communities can be resolved/unresolved."
            }

        # Check if user is community admin or discussion author
        is_community_admin = discussion.community.is_admin(user)
        is_discussion_author = discussion.author == user

        if not is_community_admin and not is_discussion_author:
            return 403, {
                "message": "Only community admins or the discussion author can resolve/unresolve discussions."
            }

        # Toggle the resolved status
        try:
            discussion.is_resolved = not discussion.is_resolved
            discussion.save(update_fields=["is_resolved"])
        except Exception as e:
            logger.error(f"Error updating discussion resolved status: {e}")
            return 500, {
                "message": "Error updating discussion status. Please try again."
            }

        # Return the updated discussion
        try:
            response_data = DiscussionOut.from_orm(discussion, user)
            return 200, response_data
        except Exception as e:
            logger.error(f"Error formatting discussion data: {e}")
            return 500, {
                "message": "Discussion updated but error retrieving discussion data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Endpoints for comments on discussions
"""


# Create a Comment
@router.post(
    "/discussions/{discussion_id}/comments/",
    response={201: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_comment(request, discussion_id: int, payload: DiscussionCommentCreateSchema):
    try:
        try:
            user = request.auth
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        is_pseudonymous = False

        if discussion.community:
            try:
                if not discussion.community.is_member(user):
                    return 403, {"message": "You are not a member of this community."}

                community_article = CommunityArticle.objects.get(
                    article=discussion.article, community=discussion.community
                )
                if community_article.is_pseudonymous:
                    is_pseudonymous = True
            except CommunityArticle.DoesNotExist:
                return 404, {"message": "Article not found in this community."}
            except Exception as e:
                logger.error(f"Error checking community membership: {e}")
                return 500, {
                    "message": "Error checking community membership. Please try again."
                }

        parent_comment = None

        if payload.parent_id:
            try:
                parent_comment = DiscussionComment.objects.get(id=payload.parent_id)

                if parent_comment.parent and parent_comment.parent.parent:
                    return 400, {
                        "message": "Exceeded maximum comment nesting level of 3"
                    }
            except DiscussionComment.DoesNotExist:
                return 404, {"message": "Parent comment not found."}
            except Exception as e:
                logger.error(f"Error retrieving parent comment: {e}")
                return 500, {
                    "message": "Error retrieving parent comment. Please try again."
                }

        try:
            comment = DiscussionComment.objects.create(
                discussion=discussion,
                community=discussion.community,
                author=user,
                content=payload.content,
                parent=parent_comment,
                is_pseudonymous=is_pseudonymous,
            )
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            return 500, {"message": "Error creating comment. Please try again."}

        if is_pseudonymous:
            try:
                # Create an anonymous name for the user who created the comment
                comment.get_anonymous_name()
            except Exception as e:
                logger.error(f"Error creating anonymous name for comment: {e}")
                # Continue even if anonymous name creation fails

        # Publish real-time event for private communities only
        try:
            if comment.community and comment.community.type == "private":
                community_ids = {comment.community.id}
                RealtimeEventPublisher.publish_comment_created(comment, community_ids)
        except Exception as e:
            logger.error(f"Failed to publish comment created event: {e}")
            # Continue even if event publishing fails

        # Return comment with replies
        try:
            return 201, DiscussionCommentOut.from_orm_with_replies(comment, user)
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {
                "message": "Comment created but error retrieving comment data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get a Comment
@router.get(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    try:
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
            return 500, {"message": "Error retrieving comment. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            comment.discussion.community
            and not comment.discussion.community.is_member(current_user)
            and comment.discussion.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, DiscussionCommentOut.from_orm_with_replies(
                comment, current_user
            )
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/discussions/{discussion_id}/comments/",
    response={200: List[DiscussionCommentOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_discussion_comments(
    request, discussion_id: int, page: int = 1, size: int = 10
):
    try:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            return 404, {"message": "Discussion not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion: {e}")
            return 500, {"message": "Error retrieving discussion. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            discussion.community
            and not discussion.community.is_member(current_user)
            and discussion.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            comments = (
                DiscussionComment.objects.filter(discussion=discussion, parent=None)
                .select_related("author")
                .order_by("-created_at")
            )
        except Exception as e:
            logger.error(f"Error retrieving comments: {e}")
            return 500, {"message": "Error retrieving comments. Please try again."}

        try:
            return 200, [
                DiscussionCommentOut.from_orm_with_replies(comment, current_user)
                for comment in comments
            ]
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/discussions/comments/{comment_id}/",
    response={200: DiscussionCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: DiscussionCommentUpdateSchema):
    try:
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
            return 500, {"message": "Error retrieving comment. Please try again."}

        if comment.author != request.auth:
            return 403, {
                "message": "You do not have permission to update this comment."
            }

        if comment.discussion.community and not comment.discussion.community.is_member(
            request.auth
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            comment.content = payload.content or comment.content
            comment.save()
        except Exception as e:
            logger.error(f"Error updating comment: {e}")
            return 500, {"message": "Error updating comment. Please try again."}

        try:
            return 200, DiscussionCommentOut.from_orm_with_replies(
                comment, request.auth
            )
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {
                "message": "Comment updated but error retrieving comment data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/comments/{comment_id}/",
    response={204: None, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_comment(request, comment_id: int):
    try:
        user = request.auth
        try:
            comment = DiscussionComment.objects.get(id=comment_id)
        except DiscussionComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
            return 500, {"message": "Error retrieving comment. Please try again."}

        # Check if the user is the owner of the comment or has permission to delete it
        if comment.author != user:
            return 403, {
                "message": "You do not have permission to delete this comment."
            }

        try:
            # Store parent info before deletion for real-time event
            parent_id = comment.parent.id if comment.parent else None
            reply_depth = 0
            current_comment = comment
            while current_comment.parent:
                reply_depth += 1
                current_comment = current_comment.parent

            # Delete reactions associated with the comment
            Reaction.objects.filter(
                content_type__model="discussioncomment", object_id=comment.id
            ).delete()

            # Logically delete the comment by clearing its content and marking it as deleted
            comment.content = "[deleted]"
            comment.is_deleted = True
            comment.save()

            # Publish real-time event for private communities only
            try:
                if comment.community and comment.community.type == "private":
                    community_ids = {comment.community.id}
                    RealtimeEventPublisher.publish_comment_deleted(
                        comment_id=comment.id,
                        discussion_id=comment.discussion.id,
                        article_id=comment.discussion.article.id,
                        community_ids=community_ids,
                        author_id=comment.author.id,
                        parent_id=parent_id,
                        reply_depth=reply_depth,
                    )
            except Exception as e:
                logger.error(f"Failed to publish comment deleted event: {e}")
                # Continue even if event publishing fails

        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            return 500, {"message": "Error deleting comment. Please try again."}

        return 204, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Subscription endpoints for discussion real-time updates
"""


@router.put(
    "/discussions/subscriptions/{subscription_id}/",
    response={200: DiscussionSubscriptionOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_discussion_subscription(
    request, subscription_id: int, update_data: DiscussionSubscriptionUpdateSchema
):
    """
    Update discussion subscription (mainly to activate/deactivate)
    """
    try:
        user = request.auth

        try:
            subscription = DiscussionSubscription.objects.select_related(
                "community_article", "community", "article"
            ).get(id=subscription_id, user=user)
        except DiscussionSubscription.DoesNotExist:
            return 404, {"message": "Subscription not found."}
        except Exception as e:
            logger.error(f"Error retrieving subscription: {e}")
            return 500, {"message": "Error retrieving subscription. Please try again."}

        try:
            # Update subscription active status
            if update_data.is_active is not None:
                subscription.is_active = update_data.is_active

            subscription.save()
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            return 500, {"message": "Error updating subscription. Please try again."}

        logger.info(f"User {user.id} updated subscription {subscription_id}")

        # Notify Tornado server about subscription change for immediate real-time updates
        try:
            from myapp.realtime import RealtimeQueueManager, get_user_community_ids

            community_ids = list(get_user_community_ids(user))
            RealtimeQueueManager.update_user_subscriptions(user.id, community_ids)
        except Exception as e:
            logger.warning(
                f"Failed to update real-time subscriptions for user {user.id}: {e}"
            )
            # Continue - real-time update failure shouldn't break subscription update

        try:
            return 200, DiscussionSubscriptionOut.from_orm(subscription)
        except Exception as e:
            logger.error(f"Error formatting subscription data: {e}")
            return 500, {
                "message": "Subscription updated but error retrieving subscription data."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/subscriptions/{subscription_id}/",
    response={204: None, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def unsubscribe_from_discussion(request, subscription_id: int):
    """
    Unsubscribe from discussion updates (soft delete by setting is_active to False)
    """
    try:
        user = request.auth

        try:
            subscription = DiscussionSubscription.objects.get(
                id=subscription_id, user=user
            )
        except DiscussionSubscription.DoesNotExist:
            return 404, {"message": "Subscription not found."}
        except Exception as e:
            logger.error(f"Error retrieving subscription: {e}")
            return 500, {"message": "Error retrieving subscription. Please try again."}

        try:
            # Soft delete by setting is_active to False
            subscription.is_active = False
            subscription.save()
        except Exception as e:
            logger.error(f"Error deactivating subscription: {e}")
            return 500, {"message": "Error unsubscribing. Please try again."}

        logger.info(f"User {user.id} unsubscribed from subscription {subscription_id}")

        # Notify Tornado server about subscription change for immediate real-time updates
        try:
            from myapp.realtime import RealtimeQueueManager, get_user_community_ids

            community_ids = list(get_user_community_ids(user))
            RealtimeQueueManager.update_user_subscriptions(user.id, community_ids)
        except Exception as e:
            logger.warning(
                f"Failed to update real-time subscriptions for user {user.id}: {e}"
            )
            # Continue - real-time update failure shouldn't break unsubscription

        return 204, None

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Discussion Summary endpoints for admin notes
Only community admins can create/update discussion summaries
"""


@router.get(
    "/discussions/summary/{community_article_id}/",
    response={200: DiscussionSummaryOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_discussion_summary(request, community_article_id: int):
    """
    Get the discussion summary for a community article.
    Available to all users who can view the article.

    Optimized: Single query with all necessary joins.
    """
    try:
        user = request.auth

        try:
            summary = DiscussionSummary.objects.select_related(
                "created_by",
                "last_updated_by",
                "community_article__community",
            ).get(community_article_id=community_article_id)
        except DiscussionSummary.DoesNotExist:
            return 404, {"message": "Discussion summary not found for this article."}
        except Exception as e:
            logger.error(f"Error retrieving discussion summary: {e}")
            return 500, {
                "message": "Error retrieving discussion summary. Please try again."
            }

        # Check if user can view (hidden communities require membership)
        community = summary.community_article.community
        if community.type == "hidden" and not community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, DiscussionSummaryOut.from_orm(summary)
        except Exception as e:
            logger.error(f"Error formatting discussion summary data: {e}")
            return 500, {
                "message": "Error formatting discussion summary data. Please try again."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/discussions/summary/{community_article_id}/",
    response={201: DiscussionSummaryOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_discussion_summary(
    request, community_article_id: int, payload: DiscussionSummaryCreateSchema
):
    """
    Create a discussion summary for a community article.
    Only community admins can create summaries.

    Optimized: Uses prefetch for admin check, atomic create with get_or_create pattern.
    """
    try:
        user = request.auth

        try:
            community_article = CommunityArticle.objects.select_related(
                "community"
            ).get(id=community_article_id)
        except CommunityArticle.DoesNotExist:
            return 404, {"message": "Community article not found."}
        except Exception as e:
            logger.error(f"Error retrieving community article: {e}")
            return 500, {
                "message": "Error retrieving community article. Please try again."
            }

        # Check if user is an admin
        if not community_article.community.is_admin(user):
            return 403, {
                "message": "Only community admins can create discussion summaries."
            }

        try:
            with transaction.atomic():
                # Use get_or_create to handle race conditions
                summary, created = DiscussionSummary.objects.get_or_create(
                    community_article=community_article,
                    defaults={
                        "content": payload.content,
                        "created_by": user,
                        "last_updated_by": user,
                    },
                )

                if not created:
                    return 400, {
                        "message": "A discussion summary already exists for this article. Use PUT to update it."
                    }

        except Exception as e:
            logger.error(f"Error creating discussion summary: {e}")
            return 500, {
                "message": "Error creating discussion summary. Please try again."
            }

        logger.info(
            f"User {user.id} created discussion summary for community article {community_article_id}"
        )

        try:
            return 201, DiscussionSummaryOut.from_orm(summary)
        except Exception as e:
            logger.error(f"Error formatting discussion summary data: {e}")
            return 500, {
                "message": "Discussion summary created but error retrieving data."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/discussions/summary/{community_article_id}/",
    response={200: DiscussionSummaryOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_discussion_summary(
    request, community_article_id: int, payload: DiscussionSummaryUpdateSchema
):
    """
    Update the discussion summary for a community article.
    Only community admins can update summaries.
    """
    try:
        user = request.auth

        try:
            summary = DiscussionSummary.objects.select_related(
                "community_article__community",
            ).get(community_article_id=community_article_id)
        except DiscussionSummary.DoesNotExist:
            return 404, {
                "message": "Discussion summary not found. Use POST to create one."
            }
        except Exception as e:
            logger.error(f"Error retrieving discussion summary: {e}")
            return 500, {
                "message": "Error retrieving discussion summary. Please try again."
            }

        # Check if user is an admin
        if not summary.community_article.community.is_admin(user):
            return 403, {
                "message": "Only community admins can update discussion summaries."
            }

        try:
            summary.content = payload.content
            summary.last_updated_by = user
            summary.save(update_fields=["content", "last_updated_by", "updated_at"])
        except Exception as e:
            logger.error(f"Error updating discussion summary: {e}")
            return 500, {
                "message": "Error updating discussion summary. Please try again."
            }

        logger.info(
            f"User {user.id} updated discussion summary for community article {community_article_id}"
        )

        try:
            return 200, DiscussionSummaryOut.from_orm(summary)
        except Exception as e:
            logger.error(f"Error formatting discussion summary data: {e}")
            return 500, {
                "message": "Discussion summary updated but error retrieving data."
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/discussions/summary/{community_article_id}/",
    response={204: None, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_discussion_summary(request, community_article_id: int):
    """
    Delete the discussion summary for a community article.
    Only community admins can delete summaries.
    """
    try:
        user = request.auth

        try:
            summary = DiscussionSummary.objects.select_related(
                "community_article__community",
            ).get(community_article_id=community_article_id)
        except DiscussionSummary.DoesNotExist:
            return 404, {"message": "Discussion summary not found."}
        except Exception as e:
            logger.error(f"Error retrieving discussion summary: {e}")
            return 500, {
                "message": "Error retrieving discussion summary. Please try again."
            }

        # Check if user is an admin
        if not summary.community_article.community.is_admin(user):
            return 403, {
                "message": "Only community admins can delete discussion summaries."
            }

        try:
            summary.delete()
        except Exception as e:
            logger.error(f"Error deleting discussion summary: {e}")
            return 500, {
                "message": "Error deleting discussion summary. Please try again."
            }

        logger.info(
            f"User {user.id} deleted discussion summary for community article {community_article_id}"
        )

        return 204, None

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
