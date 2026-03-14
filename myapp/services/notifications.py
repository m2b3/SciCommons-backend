"""
Notification Service for SciCommons

Handles notification creation (DB persistence) and realtime event publishing.
Provides a generic interface for all notification types with efficient recipient resolution.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import redis
from decouple import config
from django.db.models import Q

logger = logging.getLogger(__name__)

# Redis configuration (reuse from realtime module)
ENVIRONMENT = config("ENVIRONMENT", default="dev").lower()
if ENVIRONMENT == "staging":
    _default_redis_url = "redis://redis-test:6379/3"
else:
    _default_redis_url = "redis://redis:6379/3"

REDIS_URL = config("REALTIME_REDIS_URL", default=_default_redis_url)

# Global Redis connection
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for notifications"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


def serialize_json(obj):
    """Custom JSON serializer that handles datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class NotificationType(str, Enum):
    """All supported notification types"""

    # Join requests (community moderation)
    JOIN_REQUEST_RECEIVED = "join_request_received"  # Admin receives join request
    JOIN_REQUEST_APPROVED = "join_request_approved"  # User's request approved
    JOIN_REQUEST_REJECTED = "join_request_rejected"  # User's request rejected

    # Invitations
    INVITATION_RECEIVED = "invitation_received"  # User receives invitation
    INVITATION_RESPONDED = "invitation_responded"  # Admin notified of response

    # Articles (community moderation)
    ARTICLE_SUBMITTED = "article_submitted"  # Admin receives article submission
    ARTICLE_ASSIGNED = "article_assigned"  # Reviewer/moderator assigned to article
    ARTICLE_ACCEPTED = "article_accepted"  # Author notified of acceptance
    ARTICLE_REJECTED = "article_rejected"  # Author notified of rejection

    # Reviews
    REVIEW_SUBMITTED = "review_submitted"  # Author notified of new review
    REVIEW_COMMENT = "review_comment"  # Participant notified of review comment

    # Discussions
    DISCUSSION_CREATED = "discussion_created"  # Author notified of new discussion
    DISCUSSION_COMMENT = "discussion_comment"  # Participant notified of comment
    DISCUSSION_MENTION = "discussion_mention"  # User tagged in discussion


class NotificationCategory(str, Enum):
    """Notification categories"""

    ARTICLES = "articles"
    COMMUNITIES = "communities"
    USERS = "users"


class RecipientResolvers:
    """
    Efficient recipient resolvers for different notification scenarios.
    Each resolver returns a list of user IDs using optimized single queries.
    """

    @staticmethod
    def single_user(user_id: int) -> List[int]:
        """Single user recipient"""
        return [user_id]

    @staticmethod
    def community_admins(community_id: int) -> List[int]:
        """Get all admin IDs for a community (single query)"""
        from communities.models import Community

        return list(
            Community.objects.filter(id=community_id).values_list(
                "admins__id", flat=True
            )
        )

    @staticmethod
    def community_moderators(community_id: int) -> List[int]:
        """Get all moderator IDs for a community (single query)"""
        from communities.models import Community

        return list(
            Community.objects.filter(id=community_id).values_list(
                "moderators__id", flat=True
            )
        )

    @staticmethod
    def community_admins_and_moderators(community_id: int) -> List[int]:
        """Get all admin and moderator IDs for a community (single query)"""
        from communities.models import Community

        community = Community.objects.filter(id=community_id).first()
        if not community:
            return []

        admin_ids = set(community.admins.values_list("id", flat=True))
        moderator_ids = set(community.moderators.values_list("id", flat=True))
        return list(admin_ids | moderator_ids)

    @staticmethod
    def community_all_members(community_id: int) -> List[int]:
        """Get all member IDs for a community including admins/moderators (optimized query)"""
        from communities.models import Community
        from users.models import User

        community = Community.objects.filter(id=community_id).first()
        if not community:
            return []

        return list(
            User.objects.filter(
                Q(member_communities=community)
                | Q(admin_communities=community)
                | Q(moderator_communities=community)
            )
            .values_list("id", flat=True)
            .distinct()
        )

    @staticmethod
    def article_author(article_id: int) -> List[int]:
        """Get article submitter ID"""
        from articles.models import Article

        article = Article.objects.filter(id=article_id).first()
        if article and article.submitter_id:
            return [article.submitter_id]
        return []

    @staticmethod
    def article_reviewers(article_id: int) -> List[int]:
        """Get all reviewer IDs for an article (single query)"""
        from articles.models import Review

        return list(
            Review.objects.filter(article_id=article_id).values_list(
                "reviewer_id", flat=True
            )
        )

    @staticmethod
    def article_participants(article_id: int) -> List[int]:
        """Get article author + all reviewers (optimized)"""
        author_ids = RecipientResolvers.article_author(article_id)
        reviewer_ids = RecipientResolvers.article_reviewers(article_id)
        return list(set(author_ids + reviewer_ids))

    @staticmethod
    def community_article_moderator(community_id: int, article_id: int) -> List[int]:
        """Get the assigned moderator for a community article"""
        from communities.models import CommunityArticle

        try:
            ca = CommunityArticle.objects.filter(
                community_id=community_id, article_id=article_id
            ).first()
            if ca and ca.moderator_id:
                return [ca.moderator_id]
        except Exception:
            pass
        return []

    @staticmethod
    def community_article_reviewers(community_id: int, article_id: int) -> List[int]:
        """Get assigned reviewers for a community article"""
        from communities.models import CommunityArticle

        try:
            ca = CommunityArticle.objects.filter(
                community_id=community_id, article_id=article_id
            ).first()
            if ca:
                return list(ca.reviewers.values_list("id", flat=True))
        except Exception:
            pass
        return []


class NotificationService:
    """
    Main service for sending notifications.

    Handles:
    1. Recipient resolution (efficient DB queries)
    2. Notification DB record creation (bulk_create)
    3. Realtime event publishing to Redis
    """

    @staticmethod
    def send(
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        recipient_ids: List[int],
        link: Optional[str] = None,
        content: Optional[str] = None,
        community_id: Optional[int] = None,
        article_id: Optional[int] = None,
        exclude_user_id: Optional[int] = None,
    ) -> List[int]:
        """
        Send notifications to specified recipients.

        Args:
            notification_type: Type of notification
            category: Category of notification
            message: Notification message
            recipient_ids: List of user IDs to notify
            link: Optional link for the notification
            content: Optional additional content
            community_id: Optional community reference
            article_id: Optional article reference
            exclude_user_id: Optional user ID to exclude (e.g., the action performer)

        Returns:
            List of notification IDs created
        """
        from users.models import Notification

        if not recipient_ids:
            logger.warning(f"No recipients for notification type {notification_type}")
            return []

        # Filter out excluded user
        if exclude_user_id:
            recipient_ids = [uid for uid in recipient_ids if uid != exclude_user_id]

        if not recipient_ids:
            logger.debug(
                f"All recipients excluded for notification type {notification_type}"
            )
            return []

        # Remove duplicates
        recipient_ids = list(set(recipient_ids))

        # 1. Create DB records using bulk_create
        notifications = []
        for user_id in recipient_ids:
            notification = Notification(
                user_id=user_id,
                notification_type=notification_type.value,
                category=category.value,
                message=message,
                link=link,
                content=content,
                community_id=community_id,
                article_id=article_id,
            )
            notifications.append(notification)

        try:
            created_notifications = Notification.objects.bulk_create(notifications)
            notification_ids = [n.id for n in created_notifications]
            logger.info(
                f"Created {len(notification_ids)} notifications of type {notification_type}"
            )
        except Exception as e:
            logger.error(f"Failed to create notifications: {e}", exc_info=True)
            return []

        # 2. Publish realtime event
        NotificationService._publish_realtime_event(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=recipient_ids,
            link=link,
            content=content,
            community_id=community_id,
            article_id=article_id,
            notification_ids=notification_ids,
        )

        return notification_ids

    @staticmethod
    def send_to_user(
        user_id: int,
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        **kwargs,
    ) -> List[int]:
        """Convenience method to send notification to a single user"""
        return NotificationService.send(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=[user_id],
            **kwargs,
        )

    @staticmethod
    def send_to_community_admins(
        community_id: int,
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        exclude_user_id: Optional[int] = None,
        **kwargs,
    ) -> List[int]:
        """Convenience method to send notification to all community admins"""
        recipient_ids = RecipientResolvers.community_admins(community_id)
        return NotificationService.send(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=recipient_ids,
            community_id=community_id,
            exclude_user_id=exclude_user_id,
            **kwargs,
        )

    @staticmethod
    def send_to_community_admins_and_moderators(
        community_id: int,
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        exclude_user_id: Optional[int] = None,
        **kwargs,
    ) -> List[int]:
        """Convenience method to send notification to all community admins and moderators"""
        recipient_ids = RecipientResolvers.community_admins_and_moderators(community_id)
        return NotificationService.send(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=recipient_ids,
            community_id=community_id,
            exclude_user_id=exclude_user_id,
            **kwargs,
        )

    @staticmethod
    def send_to_community_members(
        community_id: int,
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        exclude_user_id: Optional[int] = None,
        **kwargs,
    ) -> List[int]:
        """Convenience method to send notification to all community members"""
        recipient_ids = RecipientResolvers.community_all_members(community_id)
        return NotificationService.send(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=recipient_ids,
            community_id=community_id,
            exclude_user_id=exclude_user_id,
            **kwargs,
        )

    @staticmethod
    def send_to_article_author(
        article_id: int,
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        exclude_user_id: Optional[int] = None,
        **kwargs,
    ) -> List[int]:
        """Convenience method to send notification to article author"""
        recipient_ids = RecipientResolvers.article_author(article_id)
        return NotificationService.send(
            notification_type=notification_type,
            category=category,
            message=message,
            recipient_ids=recipient_ids,
            article_id=article_id,
            exclude_user_id=exclude_user_id,
            **kwargs,
        )

    @staticmethod
    def _publish_realtime_event(
        notification_type: NotificationType,
        category: NotificationCategory,
        message: str,
        recipient_ids: List[int],
        link: Optional[str],
        content: Optional[str],
        community_id: Optional[int],
        article_id: Optional[int],
        notification_ids: List[int],
    ):
        """Publish notification event to Redis for realtime delivery"""
        try:
            event = {
                "type": "new_notification",
                "target_user_ids": recipient_ids,
                "data": {
                    "notification_type": notification_type.value,
                    "category": category.value,
                    "message": message,
                    "link": link,
                    "content": content,
                    "community_id": community_id,
                    "article_id": article_id,
                    "notification_ids": notification_ids,
                },
                "timestamp": None,  # Will be set by Tornado
                "event_id": None,  # Will be set by Tornado
            }

            redis_client = get_redis_client()
            result = redis_client.publish(
                "notification_events", json.dumps(event, default=serialize_json)
            )

            logger.info(
                f"Published {notification_type} notification event to {len(recipient_ids)} users. "
                f"Redis subscribers: {result}"
            )
            logger.debug(f"Event data: {event}")

        except Exception as e:
            logger.error(
                f"Failed to publish notification event {notification_type}: {e}",
                exc_info=True,
            )
