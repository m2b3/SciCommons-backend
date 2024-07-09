from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from ninja import ModelSchema, Schema

from articles.models import Article
from articles.schemas import ArticleOut
from communities.models import Community, JoinRequest
from myapp.schemas import Tag
from users.models import User

"""
Community management schemas for serialization and validation.
"""


class CommunityType(str, Enum):
    PUBLIC = "public"
    HIDDEN = "hidden"
    LOCKED = "locked"


class CreateCommunityDetails(Schema):
    name: str
    description: str
    tags: List[Tag]
    type: CommunityType


class CommunityCreateSchema(Schema):
    details: CreateCommunityDetails


class CommunitySchema(ModelSchema):
    id: int
    name: str
    description: str
    tags: List[Tag]
    type: CommunityType
    profile_pic_url: Optional[str]
    banner_pic_url: Optional[str]
    slug: str
    created_at: Optional[datetime]
    rules: List[str]
    num_moderators: int
    num_reviewers: int
    num_members: int
    num_published_articles: int
    num_articles: int
    is_member: bool = False
    is_moderator: bool = False
    is_reviewer: bool = False
    is_admin: bool = False
    join_request_status: Optional[str] = None

    class Config:
        model = Community
        model_fields = [
            "id",
            "name",
            "description",
            "tags",
            "type",
            "profile_pic_url",
            "banner_pic_url",
            "slug",
            "created_at",
            "rules",
        ]

    @staticmethod
    def from_orm_with_custom_fields(community: Community, user: Optional[User] = None):
        response_data = CommunitySchema(
            id=community.id,
            name=community.name,
            description=community.description,
            tags=community.tags,
            type=community.type,
            profile_pic_url=(
                community.profile_pic_url.url if community.profile_pic_url else None
            ),
            banner_pic_url=(
                community.banner_pic_url.url if community.banner_pic_url else None
            ),
            slug=community.slug,
            created_at=community.created_at,
            rules=community.rules,
            num_moderators=community.moderators.count(),
            num_reviewers=community.reviewers.count(),
            num_members=community.members.count(),
            num_published_articles=Article.objects.filter(
                community=community, published=True
            ).count(),
            num_articles=Article.objects.filter(community=community).count(),
        )

        if user and not isinstance(user, bool):
            response_data.is_member = community.members.filter(id=user.id).exists()
            response_data.is_moderator = community.moderators.filter(
                id=user.id
            ).exists()
            response_data.is_reviewer = community.reviewers.filter(id=user.id).exists()
            response_data.is_admin = community.admins.filter(id=user.id).exists()

            # Check if the user has a latest join request
            join_request = JoinRequest.objects.filter(
                community=community, user=user
            ).order_by("-id")

            if join_request.exists():
                response_data.join_request_status = join_request.first().status

        return response_data


class PaginatedCommunities(Schema):
    items: List[CommunitySchema]
    total: int
    page: int
    per_page: int


class UpdateCommunityDetails(Schema):
    description: str
    type: CommunityType
    tags: List[Tag]
    rules: List[str]


class CommunityUpdateSchema(Schema):
    details: UpdateCommunityDetails


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
    published: List[ArticleOut]
    unpublished: List[ArticleOut]
    submitted: List[ArticleOut]
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
