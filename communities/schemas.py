from datetime import datetime
from typing import List, Literal, Optional

from ninja import Schema

from articles.schemas import ArticleDetails

"""
Community management schemas for serialization and validation.
"""


class CommunityDetails(Schema):
    id: int
    name: str
    description: str
    tags: str
    type: str
    profile_pic_url: str | None
    banner_pic_url: str | None
    slug: str
    created_at: datetime | None
    rules: list[str]
    num_moderators: int
    num_reviewers: int
    num_members: int
    num_published_articles: int
    num_articles: int
    is_member: bool = False
    is_moderator: bool = False
    is_reviewer: bool = False
    is_admin: bool = False
    join_request_status: str | None = None


class CreateCommunityResponse(Schema):
    id: int
    message: str


class PaginatedCommunitySchema(Schema):
    total: int
    page: int
    size: int
    communities: List[CommunityDetails]


class CreateCommunitySchema(Schema):
    name: str
    description: str
    tags: str
    type: str


class UpdateCommunityDetails(Schema):
    description: str
    type: str
    tags: str
    rules: list[str]


"""
Invitation and join request schemas for serialization and validation.
"""


class CommunityMemberSchema(Schema):
    id: int
    username: str
    email: str


class InviteSchema(Schema):
    email: Optional[str] = None
    username: Optional[str] = None


"""
Community post schemas for serialization and validation.
"""


class CommunityPostOut(Schema):
    id: int
    title: str
    content: str
    author: str
    created_at: str
    updated_at: str


class CommunityPostDetailOut(Schema):
    id: int
    title: str
    content: str
    author: str
    community: str
    cited_article: str
    cited_url: str
    created_at: str
    updated_at: str


class CreatePostSchema(Schema):
    title: str
    content: str
    cited_article_id: Optional[int] = None
    cited_url: Optional[str] = None


class UpdatePostSchema(Schema):
    title: Optional[str] = None
    content: Optional[str] = None
    cited_article_id: Optional[int] = None
    cited_url: Optional[str] = None


class CommentIn(Schema):
    content: str


"""Invitation and join request schemas for serialization and validation."""


class InvitePayload(Schema):
    usernames: list[str]
    note: str


class InvitationResponseRequest(Schema):
    action: Literal["accept", "reject"]


class Message(Schema):
    message: str


class SendInvitationsPayload(Schema):
    emails: list[str]
    subject: str
    body: str


class InvitationDetails(Schema):
    id: int
    email: str | None
    username: str | None
    invited_at: str
    status: str


class CommunityInvitationDetails(Schema):
    name: str
    description: str
    profile_pic_url: str
    num_members: int


"""Community post schemas for serialization and validation."""


class CreateCommunityArticleDetails(Schema):
    title: str
    abstract: str
    keywords: str
    authors: str
    submission_type: str


class InvitationDetailsSchema(Schema):
    email: str | None
    name: str | None
    status: str
    date: str

    @staticmethod
    def resolve_date(obj):
        return obj.invited_at.strftime("%I:%M %p, %d %b, %Y")


"""Admin schemas for serialization and validation."""


class UserSchema(Schema):
    id: int
    username: str
    email: str
    joined_at: datetime | None
    articles_published: int


class MembersResponse(Schema):
    community_id: int
    members: List[UserSchema]
    moderators: List[UserSchema]
    reviewers: List[UserSchema]
    admins: List[UserSchema]


class AdminArticlesResponse(Schema):
    published: List[ArticleDetails]
    unpublished: List[ArticleDetails]
    submitted: List[ArticleDetails]
    community_id: int


class UserToJoin(Schema):
    id: int
    username: str
    email: str
    profile_pic_url: str | None


class JoinRequestSchema(Schema):
    id: int
    user: UserToJoin
    community_id: int
    requested_at: datetime
    status: Literal["pending", "approved", "rejected"]
    rejection_timestamp: datetime | None
