from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ninja import ModelSchema, Schema

from articles.schemas import ArticleOut
from communities.models import (
    ArticleSubmissionAssessment,
    Community,
    CommunityArticle,
    JoinRequest,
)
from myapp.schemas import UserStats
from users.models import HashtagRelation, User

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
    tags: List[str]
    type: CommunityType


class CommunityCreateSchema(Schema):
    details: CreateCommunityDetails


class CommunityOut(ModelSchema):
    id: int
    name: str
    description: str
    tags: List[str]
    type: CommunityType
    profile_pic_url: Optional[str] = None
    banner_pic_url: Optional[str] = None
    slug: str
    created_at: Optional[datetime] = None
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
            "type",
            "profile_pic_url",
            "banner_pic_url",
            "slug",
            "created_at",
            "rules",
        ]

    @staticmethod
    def from_orm_with_custom_fields(community: Community, user: Optional[User] = None):
        tags = [
            relation.hashtag.name
            for relation in HashtagRelation.objects.filter(
                content_type=ContentType.objects.get_for_model(Community),
                object_id=community.id,
            )
        ]
        num_published_articles = CommunityArticle.objects.filter(
            community=community, status="published"
        ).count()
        num_articles = CommunityArticle.objects.filter(community=community).count()
        response_data = CommunityOut(
            id=community.id,
            name=community.name,
            description=community.description,
            tags=tags,
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
            num_published_articles=num_published_articles,
            num_articles=num_articles,
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
    items: List[CommunityOut]
    total: int
    page: int
    per_page: int


class UpdateCommunityDetails(Schema):
    description: str
    type: CommunityType
    tags: List[str]
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


class ArticleStatus(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PUBLISHED = "published"


class Filters(Schema):
    status: Optional[ArticleStatus] = None
    submitted_after: Optional[datetime] = None
    submitted_before: Optional[datetime] = None


class AssessorSchema(ModelSchema):
    assessor: UserStats

    class Config:
        model = ArticleSubmissionAssessment
        model_fields = [
            "id",
            "assessor",
            "is_moderator",
            "approved",
            "comments",
            "assessed_at",
        ]

    @staticmethod
    def from_orm_with_custom_fields(assessment: ArticleSubmissionAssessment):
        return AssessorSchema(
            id=assessment.id,
            assessor=UserStats.from_model(assessment.assessor, basic_details=True),
            is_moderator=assessment.is_moderator,
            approved=assessment.approved,
            comments=assessment.comments,
            assessed_at=assessment.assessed_at,
        )


class AssessmentSubmissionSchema(Schema):
    approved: bool
    comments: str


class ArticleStatusSchema(Schema):
    status: str
    submitted_at: Optional[timezone.datetime]
    published_at: Optional[timezone.datetime]
    assessors: List[AssessorSchema]
    article: ArticleOut


"""
Assessors related schemas
"""


class AssessorArticleSchema(Schema):
    article: ArticleOut
    assessor: AssessorSchema


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


"""
Article Approval Schemas
"""
