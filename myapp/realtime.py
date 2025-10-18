"""
Real-time event system for SciCommons
Handles event publishing to Tornado server via Redis
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

import redis
from decouple import config
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

# Environment-driven defaults so compose can pass only ENVIRONMENT
ENVIRONMENT = config("ENVIRONMENT", default="dev").lower()
if ENVIRONMENT == "staging":
    _default_tornado_url = "http://tornado-test:8887"
    _default_redis_url = "redis://redis-test:6379/3"
else:
    _default_tornado_url = "http://tornado:8888"
    _default_redis_url = "redis://redis:6379/3"

# Redis and Tornado configuration (can still be overridden via env vars)
REDIS_URL = config("REALTIME_REDIS_URL", default=_default_redis_url)
TORNADO_URL = config("TORNADO_URL", default=_default_tornado_url)
TORNADO_PATH_PREFIX = config("TORNADO_PATH_PREFIX", default="/realtime")

# Global Redis connection
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for real-time events"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


def serialize_json(obj):
    """Custom JSON serializer that handles datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class EventTypes:
    """Constants for event types"""

    NEW_DISCUSSION = "new_discussion"
    NEW_COMMENT = "new_comment"
    UPDATED_DISCUSSION = "updated_discussion"
    UPDATED_COMMENT = "updated_comment"
    DELETED_DISCUSSION = "deleted_discussion"
    DELETED_COMMENT = "deleted_comment"


class RealtimeEventPublisher:
    """Publisher for real-time events to Tornado server"""

    @staticmethod
    def publish_event(
        event_type: str,
        data: Dict,
        community_ids: Set[int],
        exclude_user_id: Optional[int] = None,
    ):
        """
        Publish an event to the real-time system

        Args:
            event_type: Type of event (from EventTypes)
            data: Event data dictionary
            community_ids: Set of community IDs that should receive this event
            exclude_user_id: User ID to exclude from receiving this event (e.g., the author)
        """
        try:
            event = {
                "type": event_type,
                "data": data,
                "community_ids": list(community_ids),
                "exclude_user_id": exclude_user_id,  # User to exclude from receiving this event
                "timestamp": None,  # Will be set by Tornado
                "event_id": None,  # Will be set by Tornado
            }

            redis_client = get_redis_client()
            result = redis_client.publish(
                "discussion_events", json.dumps(event, default=serialize_json)
            )

            logger.info(
                f"Published {event_type} event for communities {community_ids}. Subscribers: {result}"
            )
            logger.debug(f"Event data: {event}")

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}", exc_info=True)

    @staticmethod
    def publish_discussion_created(discussion, community_ids: Set[int]):
        """Publish event when a new discussion is created"""
        from articles.schemas import DiscussionOut
        from communities.models import CommunityArticle

        # Create discussion output schema - pass None as current_user for real-time events
        discussion_data = DiscussionOut.from_orm(discussion, None).dict()

        # Get subscribers if this is part of a community article
        subscriber_ids = set()
        if discussion.community:
            try:
                community_article = CommunityArticle.objects.get(
                    article=discussion.article, community=discussion.community
                )
                subscriber_ids = get_discussion_subscribers(
                    community_article, discussion.community
                )
            except CommunityArticle.DoesNotExist:
                logger.warning(
                    f"No community article found for discussion {discussion.id}"
                )
            except Exception as e:
                logger.error(f"Error getting subscribers for discussion created: {e}")

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.NEW_DISCUSSION,
            data={
                "discussion": discussion_data,
                "article_id": discussion.article.id,
                "community_id": (
                    discussion.community.id if discussion.community else None
                ),
                "subscriber_ids": list(
                    subscriber_ids
                ),  # Include subscriber IDs in the event
            },
            community_ids=community_ids,
            exclude_user_id=discussion.author.id,  # Exclude the discussion author
        )

    @staticmethod
    def publish_comment_created(comment, community_ids: Set[int]):
        """Publish event when a new comment is created"""
        from articles.schemas import DiscussionCommentOut
        from communities.models import CommunityArticle

        # Create comment output schema - pass None as current_user for real-time events
        comment_data = DiscussionCommentOut.from_orm_with_replies(comment, None).dict()

        # Calculate reply depth for nested comments
        reply_depth = 0
        current_comment = comment
        while current_comment.parent:
            reply_depth += 1
            current_comment = current_comment.parent

        # Get subscribers if this is part of a community article
        subscriber_ids = set()
        if comment.community:
            try:
                community_article = CommunityArticle.objects.get(
                    article=comment.discussion.article, community=comment.community
                )
                # For replies, include users who want reply notifications
                include_reply_notifications = comment.parent is not None
                subscriber_ids = get_comment_subscribers(
                    community_article,
                    comment.community,
                    include_reply_notifications=include_reply_notifications,
                )
            except CommunityArticle.DoesNotExist:
                logger.warning(f"No community article found for comment {comment.id}")
            except Exception as e:
                logger.error(f"Error getting subscribers for comment created: {e}")

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.NEW_COMMENT,
            data={
                "comment": comment_data,
                "discussion_id": comment.discussion.id,
                "article_id": comment.discussion.article.id,
                "community_id": comment.community.id if comment.community else None,
                # Add nested reply metadata for frontend tree handling
                "parent_id": comment.parent.id if comment.parent else None,
                "is_reply": comment.parent is not None,
                "reply_depth": reply_depth,
                "subscriber_ids": list(
                    subscriber_ids
                ),  # Include subscriber IDs in the event
            },
            community_ids=community_ids,
            exclude_user_id=comment.author.id,  # Exclude the comment author
        )

    @staticmethod
    def publish_discussion_updated(discussion, community_ids: Set[int]):
        """Publish event when a discussion is updated"""
        from articles.schemas import DiscussionOut

        discussion_data = DiscussionOut.from_orm(discussion, None).dict()

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.UPDATED_DISCUSSION,
            data={
                "discussion": discussion_data,
                "article_id": discussion.article.id,
                "community_id": (
                    discussion.community.id if discussion.community else None
                ),
            },
            community_ids=community_ids,
            exclude_user_id=discussion.author.id,  # Exclude the discussion author
        )

    @staticmethod
    def publish_comment_updated(comment, community_ids: Set[int]):
        """Publish event when a comment is updated"""
        from articles.schemas import DiscussionCommentOut

        comment_data = DiscussionCommentOut.from_orm_with_replies(comment, None).dict()

        # Calculate reply depth for nested comments
        reply_depth = 0
        current_comment = comment
        while current_comment.parent:
            reply_depth += 1
            current_comment = current_comment.parent

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.UPDATED_COMMENT,
            data={
                "comment": comment_data,
                "discussion_id": comment.discussion.id,
                "article_id": comment.discussion.article.id,
                "community_id": comment.community.id if comment.community else None,
                # Add nested reply metadata for frontend tree handling
                "parent_id": comment.parent.id if comment.parent else None,
                "is_reply": comment.parent is not None,
                "reply_depth": reply_depth,
            },
            community_ids=community_ids,
            exclude_user_id=comment.author.id,  # Exclude the comment author
        )

    @staticmethod
    def publish_discussion_deleted(
        discussion_id: int,
        article_id: int,
        community_ids: Set[int],
        author_id: Optional[int] = None,
    ):
        """Publish event when a discussion is deleted"""
        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.DELETED_DISCUSSION,
            data={
                "discussion_id": discussion_id,
                "article_id": article_id,
            },
            community_ids=community_ids,
            exclude_user_id=author_id,  # Exclude the discussion author if provided
        )

    @staticmethod
    def publish_comment_deleted(
        comment_id: int,
        discussion_id: int,
        article_id: int,
        community_ids: Set[int],
        author_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        reply_depth: int = 0,
    ):
        """Publish event when a comment is deleted"""
        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.DELETED_COMMENT,
            data={
                "comment_id": comment_id,
                "discussion_id": discussion_id,
                "article_id": article_id,
                # Add nested reply metadata for frontend tree handling
                "parent_id": parent_id,
                "is_reply": parent_id is not None,
                "reply_depth": reply_depth,
            },
            community_ids=community_ids,
            exclude_user_id=author_id,  # Exclude the comment author if provided
        )


class RealtimeQueueManager:
    """Manager for interacting with Tornado queues"""

    @staticmethod
    def register_user_queue(user_id: int, community_ids: List[int]) -> Dict:
        """
        Register a new queue for a user with Tornado

        Args:
            user_id: ID of the user
            community_ids: List of community IDs the user belongs to

        Returns:
            Dictionary with queue_id and last_event_id
        """
        import requests

        try:
            response = requests.post(
                f"{TORNADO_URL}{TORNADO_PATH_PREFIX}/register",
                json={"user_id": user_id, "community_ids": community_ids},
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Failed to register queue: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error registering queue: {e}")
            return None

    @staticmethod
    def send_heartbeat(queue_id: str) -> bool:
        """
        Send heartbeat to keep queue alive

        Args:
            queue_id: ID of the queue

        Returns:
            True if successful, False otherwise
        """
        import requests

        try:
            response = requests.post(
                f"{TORNADO_URL}{TORNADO_PATH_PREFIX}/heartbeat",
                json={"queue_id": queue_id},
                timeout=5,
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False

    @staticmethod
    def update_user_subscriptions(user_id: int, community_ids: List[int]) -> bool:
        """
        Update user's subscription list in Tornado server

        Call this after subscribe/unsubscribe to immediately update the user's queue

        Args:
            user_id: ID of the user
            community_ids: Updated list of community IDs the user is subscribed to

        Returns:
            True if successful, False otherwise
        """
        import requests

        try:
            response = requests.post(
                f"{TORNADO_URL}{TORNADO_PATH_PREFIX}/update-subscriptions",
                json={"user_id": user_id, "community_ids": community_ids},
                timeout=5,
            )

            if response.status_code == 200:
                logger.info(
                    f"Updated subscriptions for user {user_id}: {community_ids}"
                )
                return True
            else:
                logger.warning(
                    f"Failed to update subscriptions for user {user_id}: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating user subscriptions: {e}")
            return False


def get_user_community_ids(user) -> Set[int]:
    """
    Get all community IDs that a user belongs to or is subscribed to (only private communities for real-time)

    Args:
        user: User instance

    Returns:
        Set of community IDs
    """
    from communities.models import Community

    # Get all private communities the user is a member of
    community_ids = set()

    # Member communities
    member_communities = user.member_communities.filter(type=Community.PRIVATE)
    community_ids.update(member_communities.values_list("id", flat=True))

    # Admin communities
    admin_communities = user.admin_communities.filter(type=Community.PRIVATE)
    community_ids.update(admin_communities.values_list("id", flat=True))

    # Moderator communities
    moderator_communities = user.moderator_communities.filter(type=Community.PRIVATE)
    community_ids.update(moderator_communities.values_list("id", flat=True))

    # Reviewer communities
    reviewer_communities = user.reviewer_communities.filter(type=Community.PRIVATE)
    community_ids.update(reviewer_communities.values_list("id", flat=True))

    # Subscribed communities (only private ones with active subscriptions)
    try:
        from articles.models import DiscussionSubscription

        subscribed_communities = DiscussionSubscription.objects.filter(
            user=user, is_active=True, community__type=Community.PRIVATE
        ).values_list("community_id", flat=True)
        community_ids.update(subscribed_communities)
    except Exception as e:
        logger.error(f"Error getting subscribed communities for user {user.id}: {e}")

    return community_ids


def get_user_subscribed_community_articles(user) -> Set[int]:
    """
    Get all community article IDs that a user is subscribed to

    Args:
        user: User instance

    Returns:
        Set of community article IDs
    """
    try:
        from articles.models import DiscussionSubscription

        subscribed_article_ids = set(
            DiscussionSubscription.objects.filter(
                user=user, is_active=True
            ).values_list("community_article_id", flat=True)
        )
        return subscribed_article_ids
    except Exception as e:
        logger.error(
            f"Error getting subscribed community articles for user {user.id}: {e}"
        )
        return set()


def get_discussion_subscribers(community_article, community) -> Set[int]:
    """
    Get all user IDs who are subscribed to discussions for a specific community article

    Args:
        community_article: CommunityArticle instance
        community: Community instance

    Returns:
        Set of user IDs who are subscribed
    """
    from articles.models import DiscussionSubscription

    try:
        subscriber_ids = set(
            DiscussionSubscription.objects.filter(
                community_article=community_article,
                community=community,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        return subscriber_ids
    except Exception as e:
        logger.error(f"Error getting discussion subscribers: {e}")
        return set()


def get_comment_subscribers(
    community_article, community, include_reply_notifications=False
) -> Set[int]:
    """
    Get all user IDs who are subscribed to comment notifications for a specific community article
    Simplified - all active subscribers get all notifications (discussions, comments, replies)

    Args:
        community_article: CommunityArticle instance
        community: Community instance
        include_reply_notifications: Not used anymore, kept for compatibility

    Returns:
        Set of user IDs who are subscribed
    """
    from articles.models import DiscussionSubscription

    try:
        # All active subscribers get all types of notifications
        subscriber_ids = set(
            DiscussionSubscription.objects.filter(
                community_article=community_article,
                community=community,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        return subscriber_ids
    except Exception as e:
        logger.error(f"Error getting comment subscribers: {e}")
        return set()


def should_user_receive_event(
    user_id: int, community_id: int, subscriber_ids: Set[int] = None
) -> bool:
    """
    Check if a user should receive an event based on community membership and subscriptions

    Args:
        user_id: User ID to check
        community_id: Community ID the event is for
        subscriber_ids: Set of user IDs who are subscribed to this specific article (optional)

    Returns:
        True if user should receive the event, False otherwise
    """
    from communities.models import Community
    from users.models import User

    try:
        # If specific subscriber_ids are provided, check if user is in that list
        if subscriber_ids is not None:
            return user_id in subscriber_ids

        # Fallback: Check if user is a member/admin/moderator of the community
        user = User.objects.get(id=user_id)
        community = Community.objects.get(id=community_id)

        return (
            community.members.filter(id=user_id).exists()
            or community.admins.filter(id=user_id).exists()
            or community.moderators.filter(id=user_id).exists()
        )
    except Exception as e:
        logger.error(f"Error checking if user {user_id} should receive event: {e}")
        return False
