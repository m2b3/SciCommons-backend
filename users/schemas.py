"""
This module defines the input and output schemas for user authentication actions
and other user-related actions.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Max
from ninja import ModelSchema, Schema

from articles.models import Review, ReviewComment
from users.config_constants import UserConfigKey, UserConfigType
from users.models import HashtagRelation, Reputation, User

"""
Users's CRUD and Authentication Schemas
"""


class UserCreateSchema(Schema):
    """
    Input schema for creating a new user. Requires username, email, password,
    first name, and last name.
    """

    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LogInSchemaIn(Schema):
    """
    Input schema for user log in. Requires a login identifier (could be
    username or email) and a password.
    """

    login: str
    password: str


class LogInUserSchemaOut(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class LogInSchemaOut(Schema):
    """
    Output schema for user log in responses. Indicates the status of the
    login attempt and provides a corresponding message.
    """

    status: str
    message: str
    token: str
    user: LogInUserSchemaOut


class ResetPasswordSchema(Schema):
    """
    Input schema for resetting a user's password. Requires the user's email.
    """

    password: str
    confirm_password: str


class AcademicStatusSchema(Schema):
    academic_email: str
    start_year: str
    end_year: Optional[str] = None


class UserBasicDetails(Schema):
    id: int
    username: str
    profile_pic_url: str

    @staticmethod
    def from_model(user: User):
        return {
            "id": user.id,
            "username": user.username,
            "profile_pic_url": user.profile_pic_url,
        }


class UserDetails(ModelSchema):
    academic_statuses: List[AcademicStatusSchema]
    research_interests: List[str]
    reputation_score: int
    reputation_level: str

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "profile_pic_url",
            "pubMed_url",
            "google_scholar_url",
            "bio",
            "home_page_url",
            "linkedin_url",
            "github_url",
            "academic_statuses",
        ]

    @staticmethod
    def resolve_user(user: User):
        # Todo: Create Reputation once a user is created
        reputation, created = Reputation.objects.get_or_create(user=user)

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_pic_url": user.profile_pic_url,
            "pubMed_url": user.pubMed_url,
            "google_scholar_url": user.google_scholar_url,
            "bio": user.bio,
            "home_page_url": user.home_page_url,
            "linkedin_url": user.linkedin_url,
            "github_url": user.github_url,
            "academic_statuses": user.academic_statuses,
            "research_interests": [
                relation.hashtag.name
                for relation in HashtagRelation.objects.filter(
                    content_type=ContentType.objects.get_for_model(User),
                    object_id=user.id,
                )
            ],
            "reputation_score": reputation.score,
            "reputation_level": reputation.level,
        }


class UserUpdateDetails(Schema):
    first_name: Optional[str]
    last_name: Optional[str]
    bio: Optional[str]
    google_scholar_url: Optional[str]
    home_page_url: Optional[str]
    linkedin_url: Optional[str]
    github_url: Optional[str]
    academic_statuses: Optional[List[AcademicStatusSchema]]
    research_interests: Optional[List[str]]


class UserUpdateSchema(Schema):
    details: UserUpdateDetails


"""
Users Content Schemas
"""


class UserArticleSchema(Schema):
    title: str
    slug: str
    status: str
    date: date

    @staticmethod
    def from_orm_bulk(articles, article_ids: list) -> list["UserArticleSchema"]:
        """
        Batch-resolve status and date for all articles using 4 bulk queries
        instead of 4 queries per article.
        """
        has_comment = set(
            ReviewComment.objects.filter(review__article_id__in=article_ids)
            .values_list("review__article_id", flat=True)
            .distinct()
        )

        has_review = set(
            Review.objects.filter(article_id__in=article_ids).values_list("article_id", flat=True).distinct()
        )

        latest_comment_dates = dict(
            ReviewComment.objects.filter(review__article_id__in=article_ids)
            .values("review__article_id")
            .annotate(latest=Max("created_at"))
            .values_list("review__article_id", "latest")
        )

        latest_review_dates = dict(
            Review.objects.filter(article_id__in=article_ids)
            .values("article_id")
            .annotate(latest=Max("created_at"))
            .values_list("article_id", "latest")
        )

        results = []
        for article in articles:
            aid = article.id
            if aid in has_comment:
                status = "Commented"
            elif aid in has_review:
                status = "Reviewed"
            else:
                status = "Submitted"

            comment_date = latest_comment_dates.get(aid)
            review_date = latest_review_dates.get(aid)
            if comment_date:
                resolved_date = comment_date.date()
            elif review_date:
                resolved_date = review_date.date()
            else:
                resolved_date = article.created_at.date()

            results.append(
                UserArticleSchema(
                    title=article.title,
                    slug=article.slug,
                    status=status,
                    date=resolved_date,
                )
            )
        return results


class UserCommunitySchema(Schema):
    name: str
    role: str
    members_count: int


class UserPostSchema(Schema):
    id: int
    title: str
    created_at: datetime
    likes_count: int
    action: str
    action_date: datetime


class FavoriteItemSchema(Schema):
    title: str
    type: str
    details: str
    tag: str
    slug: str


"""
Notification Schemas
"""


class NotificationSchema(Schema):
    id: int
    message: str
    content: Optional[str]
    isRead: bool
    link: Optional[str]
    category: str
    notificationType: str
    createdAt: datetime
    expiresAt: datetime | None


class MarkNotificationsReadSchema(Schema):
    notification_ids: List[int]


class MarkNotificationsReadResponseSchema(Schema):
    message: str
    updated_count: int


class RealtimeNotificationData(Schema):
    """Schema for realtime notification event data (sent via Tornado)"""

    notification_type: str
    category: str
    message: str
    link: Optional[str]
    content: Optional[str]
    community_id: Optional[int]
    article_id: Optional[int]
    notification_ids: list[int]


"""
Reaction Schemas
"""


class ContentTypeEnum(str, Enum):
    ARTICLE = "articles.article"
    COMMUNITY = "communities.community"
    POST = "posts.post"
    COMMENT = "posts.comment"
    REVIEWCOMMENT = "articles.reviewcomment"
    REVIEW = "articles.review"
    DISCUSSION = "articles.discussion"
    DISCUSSIONCOMMENT = "articles.discussioncomment"


class BookmarkContentTypeEnum(str, Enum):
    """Enum for content types that can be bookmarked."""

    ARTICLE = "articles.article"
    COMMUNITY = "communities.community"


class VoteEnum(int, Enum):
    LIKE = 1
    DISLIKE = -1


class ReactionIn(Schema):
    content_type: ContentTypeEnum
    object_id: int
    vote: VoteEnum


class ReactionOut(Schema):
    id: Optional[int]
    user_id: int
    vote: Optional[VoteEnum]
    created_at: Optional[str]
    message: str


class ReactionCountOut(Schema):
    likes: int
    dislikes: int
    user_reaction: VoteEnum | None


"""
Hashtag Schemas
"""


class SortEnum(str, Enum):
    POPULAR = "popular"
    RECENT = "recent"
    ALPHABETICAL = "alphabetical"


class HashtagOut(Schema):
    name: str
    count: int


class PaginatedHashtagOut(Schema):
    items: List[HashtagOut]
    total: int
    page: int
    per_page: int
    pages: int


"""
Bookmark Schemas
"""


class BookmarkSchema(Schema):
    id: int
    title: str
    type: str
    details: str
    slug: str
    created_at: datetime


class BookmarkToggleSchema(Schema):
    content_type: BookmarkContentTypeEnum
    object_id: int


class BookmarkToggleResponseSchema(Schema):
    message: str
    is_bookmarked: bool


class BookmarkStatusResponseSchema(Schema):
    is_bookmarked: Optional[bool]


class BookmarkFilterTypeEnum(str, Enum):
    """Enum for filtering bookmarks by type."""

    ARTICLE = "article"
    COMMUNITY = "community"
    ALL = "all"


class PaginatedBookmarksResponseSchema(Schema):
    items: List[BookmarkSchema]
    total: int
    page: int
    per_page: int
    pages: int


"""
User Settings Schemas
"""


class UserSettingSchema(Schema):
    """Schema for a single user setting."""

    config_name: UserConfigKey
    value: bool | int | str
    config_type: UserConfigType


class UserSettingsResponseSchema(Schema):
    """Schema for getting all user settings."""

    settings: List[UserSettingSchema]


class UserSettingUpdateSchema(Schema):
    """Schema for updating a single setting."""

    config_name: UserConfigKey
    value: bool | int | str


class UserSettingsBulkUpdateSchema(Schema):
    """Schema for bulk updating user settings."""

    settings: List[UserSettingUpdateSchema]


class UserSettingsUpdateResponseSchema(Schema):
    """Response schema for settings update."""

    message: str
    updated_count: int


class UserSettingsResetResponseSchema(Schema):
    """Response schema for settings reset."""

    message: str
    reset_count: int
