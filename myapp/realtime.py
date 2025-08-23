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

logger = logging.getLogger(__name__)

# Redis connection for real-time events
REDIS_URL = config("REALTIME_REDIS_URL", default="redis://localhost:6379/3")
TORNADO_URL = config("TORNADO_URL", default="http://localhost:8888")

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

        # Create discussion output schema - pass None as current_user for real-time events
        discussion_data = DiscussionOut.from_orm(discussion, None).dict()

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.NEW_DISCUSSION,
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
    def publish_comment_created(comment, community_ids: Set[int]):
        """Publish event when a new comment is created"""
        from articles.schemas import DiscussionCommentOut

        # Create comment output schema - pass None as current_user for real-time events
        comment_data = DiscussionCommentOut.from_orm_with_replies(comment, None).dict()

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.NEW_COMMENT,
            data={
                "comment": comment_data,
                "discussion_id": comment.discussion.id,
                "article_id": comment.discussion.article.id,
                "community_id": comment.community.id if comment.community else None,
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

        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.UPDATED_COMMENT,
            data={
                "comment": comment_data,
                "discussion_id": comment.discussion.id,
                "article_id": comment.discussion.article.id,
                "community_id": comment.community.id if comment.community else None,
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
    ):
        """Publish event when a comment is deleted"""
        RealtimeEventPublisher.publish_event(
            event_type=EventTypes.DELETED_COMMENT,
            data={
                "comment_id": comment_id,
                "discussion_id": discussion_id,
                "article_id": article_id,
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
                f"{TORNADO_URL}/realtime/register",
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
                f"{TORNADO_URL}/realtime/heartbeat",
                json={"queue_id": queue_id},
                timeout=5,
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False


def get_user_community_ids(user) -> Set[int]:
    """
    Get all community IDs that a user belongs to (only private communities for real-time)

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

    return community_ids
