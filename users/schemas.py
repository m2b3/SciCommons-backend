"""
This module defines the input and output schemas for user authentication actions
and other user-related actions.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from ninja import ModelSchema, Schema

from articles.models import Article, Review, ReviewComment
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


class LogInSchemaOut(Schema):
    """
    Output schema for user log in responses. Indicates the status of the
    login attempt and provides a corresponding message.
    """

    status: str
    message: str
    token: str


class ResetPasswordSchema(Schema):
    """
    Input schema for resetting a user's password. Requires the user's email.
    """

    password: str
    confirm_password: str
    token: str


class AcademicStatusSchema(Schema):
    academic_email: str
    start_year: str
    end_year: Optional[str] = None


class UserDetails(ModelSchema):
    academic_statuses: List[AcademicStatusSchema]
    research_interests: List[str]
    reputation_score: int
    reputation_level: str

    class Config:
        model = User
        model_fields = [
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
    def resolve_status(article: Article):
        if ReviewComment.objects.filter(review__article=article).exists():
            return "Commented"
        elif Review.objects.filter(article=article).exists():
            return "Reviewed"
        else:
            return "Submitted"

    @staticmethod
    def resolve_date(article: Article):
        comment = (
            ReviewComment.objects.filter(review__article=article)
            .order_by("-created_at")
            .first()
        )
        if comment:
            return comment.created_at.date()
        review = Review.objects.filter(article=article).order_by("-created_at").first()
        if review:
            return review.created_at.date()
        return article.created_at.date()


class UserCommunitySchema(Schema):
    name: str
    role: str
    members_count: int


class UserPostSchema(Schema):
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


"""
Reaction Schemas
"""


class ContentTypeEnum(str, Enum):
    ARTICLE = "articles.article"
    POST = "posts.post"
    COMMENT = "posts.comment"
    REVIEWCOMMENT = "articles.reviewcomment"
    REVIEW = "articles.review"
    DISCUSSION = "articles.discussion"
    DISCUSSIONCOMMENT = "articles.discussioncomment"


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


class BookmarkToggleSchema(Schema):
    content_type: ContentTypeEnum
    object_id: int


class BookmarkToggleResponseSchema(Schema):
    message: str
    is_bookmarked: bool


class BookmarkStatusResponseSchema(Schema):
    is_bookmarked: bool
