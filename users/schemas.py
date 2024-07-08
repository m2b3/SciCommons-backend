"""
This module defines the input and output schemas for user authentication actions
and other user-related actions.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from ninja import Schema


class SignUpSchemaIn(Schema):
    """
    Input schema for user sign up. Requires username, first and last name,
    email, password, and password confirmation.
    """

    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class SignUpSchemaOut(Schema):
    """
    Output schema for user sign up responses. Indicates the status of the
    registration attempt and provides a corresponding message.
    """

    status: str
    message: str


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


class EmailSchema(Schema):
    """
    Schema for email addresses.
    """

    email: str


class StatusMessageSchema(Schema):
    """
    Schema for status messages.
    """

    status: str
    message: str


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


class Message(Schema):
    message: str


"""
Reaction Schemas
"""


class ContentTypeEnum(str, Enum):
    ARTICLE = "articles.article"
    POST = "posts.post"
    COMMENT = "posts.comment"
    REVIEWCOMMENT = "articles.reviewcomment"
    REVIEW = "articles.review"


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
