"""
Common schema for all the models
"""

from datetime import date
from enum import Enum
from typing import Any, Optional

from ninja import ModelSchema, Schema

from articles.models import Article, Review, ReviewComment
from communities.models import Community
from posts.models import Comment, Post
from users.models import Reputation, User


class Tag(Schema):
    value: str
    label: str


# Generic Pagination schema
# The disadvantage of this approach is that proper response schema is not
# generated for the paginated response.


class Message(Schema):
    message: str


class UserStats(ModelSchema):
    reputation_score: Optional[int] = None
    reputation_level: Optional[str] = None
    # submitted, reviewed or commented articles
    contributed_articles: Optional[int] = None
    # communities joined
    communities_joined: Optional[int] = None
    # posts created or commented
    contributed_posts: Optional[int] = None

    class Config:
        model = User
        model_fields = ["id", "username", "bio", "profile_pic_url", "home_page_url"]

    @staticmethod
    def from_model(
        user: User,
        basic_details: bool = False,
        basic_details_with_reputation: bool = False,
    ):
        basic_data = {
            "id": user.id,
            "username": user.username,
            "profile_pic_url": user.profile_pic_url,
        }

        if basic_details:
            return UserStats(**basic_data)

        reputation, created = Reputation.objects.get_or_create(user=user)
        if basic_details_with_reputation:
            basic_data["reputation_score"] = reputation.score
            basic_data["reputation_level"] = reputation.level
            return UserStats(**basic_data)

        contributed_articles = (
            Article.objects.filter(submitter=user).count()
            + Review.objects.filter(user=user).count()
            + ReviewComment.objects.filter(author=user).count()
        )
        contributed_posts = (
            Post.objects.filter(author=user).count()
            + Comment.objects.filter(author=user).count()
        )
        community_joined = Community.objects.filter(members=user).count()

        return UserStats(
            **basic_data,
            bio=user.bio,
            home_page_url=user.home_page_url,
            contributed_articles=contributed_articles,
            communities_joined=community_joined,
            contributed_posts=contributed_posts,
        )


class FilterType(str, Enum):
    POPULAR = "popular"
    RECENT = "recent"
    RELEVANT = "relevant"


class DateCount(Schema):
    date: date
    count: int

    @classmethod
    def json_encode(cls, obj: Any) -> Any:
        if isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        return obj


class PermissionCheckOut(Schema):
    has_permission: bool


# Real-time system schemas
class RealtimeRegisterOut(Schema):
    queue_id: str
    last_event_id: int
    communities: list[int]


class RealtimeStatusOut(Schema):
    user_id: int
    communities: list[int]
    subscribed_articles: list[int] = []
    realtime_enabled: bool
    tornado_url: str


class RealtimeHeartbeatOut(Schema):
    message: str


# ============================================================================
# Flag System Types
# ============================================================================


class FlagType(str, Enum):
    """
    Available flag types that can be set on entities.
    Keep in sync with UserFlag.VALID_FLAG_TYPES in articles/models.py

    - unread: Entity has not been read by the user

    Future flags (add here and in UserFlag.VALID_FLAG_TYPES when implemented):
    - pinned: Entity is pinned by the user
    - starred: Entity is starred/favorited by the user
    - muted: Entity notifications are muted by the user
    """

    UNREAD = "unread"
    # PINNED = "pinned"
    # STARRED = "starred"
    # MUTED = "muted"


class EntityType(str, Enum):
    """
    Entity types that can have flags attached.
    Keep in sync with UserFlag.VALID_ENTITY_TYPES in articles/models.py

    - discussion: A discussion thread on an article
    - comment: A comment or reply within a discussion
    - notification: A user notification

    Future entity types (add here and in UserFlag.VALID_ENTITY_TYPES when implemented):
    - article: An article
    - review: A review on an article
    """

    DISCUSSION = "discussion"
    COMMENT = "comment"
    NOTIFICATION = "notification"
    # ARTICLE = "article"
    # REVIEW = "review"
