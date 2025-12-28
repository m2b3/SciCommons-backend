from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from django.contrib.contenttypes.models import ContentType
from ninja import ModelSchema, Schema

from articles.schemas import ArticleBasicOut
from communities.models import Community, CommunityArticle, JoinRequest
from myapp.constants import COMMUNITY_SETTINGS
from myapp.schemas import DateCount, FilterType
from users.models import HashtagRelation, User

"""
Community management schemas for serialization and validation.
"""


class CommunityType(str, Enum):
    PUBLIC = Community.PUBLIC
    PRIVATE = Community.PRIVATE
    HIDDEN = Community.HIDDEN


class CreateCommunityDetails(Schema):
    name: str
    description: str
    # tags: Optional[List[str]] = []
    type: CommunityType
    community_settings: Optional[str] = None


class CommunityCreateSchema(Schema):
    details: CreateCommunityDetails


class CommunityListOut(ModelSchema):
    id: int
    name: str
    description: str
    type: CommunityType
    slug: str
    created_at: Optional[datetime] = None
    num_members: int
    num_published_articles: int
    org: Optional[str] = None
    is_bookmarked: Optional[bool] = None
    # is_admin: bool = False
    # is_member: bool = False
    # is_request_sent: bool = False
    # requested_at: Optional[datetime] = None

    class Config:
        model = Community
        model_fields = [
            "id",
            "name",
            "description",
            "type",
            "slug",
            "created_at",
        ]

    @staticmethod
    def from_orm_with_custom_fields(
        community: Community,
        user: Optional[User] = None,
        org: Optional[str] = None,
        is_bookmarked: Optional[bool] = None,
    ):
        num_published_articles = CommunityArticle.objects.filter(
            community=community, status="published"
        ).count()
        num_members = community.members.count()
        response_data = {
            "id": community.id,
            "name": community.name,
            "description": community.description,
            "type": community.type,
            "slug": community.slug,
            "created_at": community.created_at,
            "num_members": num_members,
            "num_published_articles": num_published_articles,
            "org": org,
            "is_bookmarked": is_bookmarked,
        }

        # if user and not isinstance(user, bool):
        #     if community.is_member(user):
        #         response_data["is_member"] = True
        #     elif community.is_admin(user):
        #         response_data["is_admin"] = True
        #     else:
        #         # Check if the user has a latest join request
        #         join_request = JoinRequest.objects.filter(
        #             community=community, user=user
        #         ).order_by("-id")

        #         if join_request.exists():
        #             response_data["is_request_sent"] = True
        #             response_data["requested_at"] = join_request.first().requested_at

        return CommunityListOut(**response_data)


class CommunityOut(ModelSchema):
    id: int
    name: str
    description: str
    type: CommunityType
    slug: str
    about: dict
    num_moderators: int
    num_reviewers: int
    num_members: int
    num_published_articles: int
    num_articles: int
    created_at: Optional[datetime] = None
    profile_pic_url: Optional[str] = None
    banner_pic_url: Optional[str] = None
    tags: Optional[list[str]] = None
    rules: Optional[list[str]] = None
    is_member: Optional[bool] = None
    is_moderator: Optional[bool] = None
    is_reviewer: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_bookmarked: Optional[bool] = None
    join_request_status: Optional[str] = None
    community_settings: Optional[str] = None

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
            "about",
        ]

    @staticmethod
    def from_orm_with_custom_fields(
        community: Community,
        user: Optional[User] = None,
        is_bookmarked: Optional[bool] = None,
    ):
        num_published_articles = CommunityArticle.objects.filter(
            community=community, status="published"
        ).count()
        num_articles = CommunityArticle.objects.filter(community=community).count()
        response_data = {
            "id": community.id,
            "name": community.name,
            "description": community.description,
            "type": community.type,
            "slug": community.slug,
            "about": community.about,
            "num_moderators": community.moderators.count(),
            "num_reviewers": community.reviewers.count(),
            "num_members": community.members.count(),
            "num_published_articles": num_published_articles,
            "num_articles": num_articles,
            "community_settings": community.community_settings,
            "is_bookmarked": is_bookmarked,
        }

        if community.created_at:
            response_data["created_at"] = community.created_at

        if community.profile_pic_url:
            response_data["profile_pic_url"] = community.profile_pic_url.url

        if community.banner_pic_url:
            response_data["banner_pic_url"] = community.banner_pic_url.url

        # if tags
        # tags = [
        #     relation.hashtag.name
        #     for relation in HashtagRelation.objects.filter(
        #         content_type=ContentType.objects.get_for_model(Community),
        #         object_id=community.id,
        #     )
        # ]
        # tags = []

        if user and not isinstance(user, bool):
            if community.is_member(user):
                response_data.update(
                    {
                        "is_member": True,
                        "is_moderator": community.moderators.filter(
                            id=user.id
                        ).exists(),
                        "is_reviewer": community.reviewers.filter(id=user.id).exists(),
                        "is_admin": community.is_admin(user),
                        "rules": community.rules if community.rules else None,
                    }
                )

            else:
                # Checking if the user has a latest join request
                join_request = JoinRequest.objects.filter(
                    community=community, user=user
                ).order_by("-id")

                if join_request.exists():
                    response_data["join_request_status"] = join_request.first().status

        return CommunityOut(**response_data)


class PaginatedCommunities(Schema):
    items: List[CommunityListOut]
    total: int
    page: int
    per_page: int
    num_pages: int


class UpdateCommunityDetails(Schema):
    description: str
    type: CommunityType
    rules: Optional[List[str]] = [""]
    community_settings: Optional[str] = None
    # tags: List[str]
    # about: dict


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
    UNPUBLISHED = "unpublished"


class Filters(Schema):
    status: Optional[ArticleStatus] = None
    submitted_after: Optional[datetime] = None
    submitted_before: Optional[datetime] = None


"""
Assessors related schemas
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
    # profile_pic_url: str
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


"""Community Members Related schemas for serialization and validation."""


class UserSchema(Schema):
    id: int
    username: str
    email: str
    profile_pic_url: str | None
    joined_at: datetime | None
    articles_submitted: int
    articles_published: int
    articles_reviewed: int


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
Relevant Communities schemas for serialization and validation.
"""


class CommunityFilters(Schema):
    offset: int = 0
    limit: int = 10
    filter_type: FilterType = "recent"  # Can be "popular", "recent", or "relevant"


class CommunityBasicOut(Schema):
    id: int
    name: str
    profile_pic_url: Optional[str]
    total_published_articles: int
    total_members: int

    @staticmethod
    def from_orm(community: Community):
        return CommunityBasicOut(
            id=community.id,
            name=community.name,
            profile_pic_url=(
                community.profile_pic_url.url if community.profile_pic_url else None
            ),
            total_published_articles=CommunityArticle.objects.filter(
                community=community, status="published"
            ).count(),
            total_members=community.members.count(),
        )


"""
Community Stats schemas for serialization and validation.
"""


class CommunityStatsResponse(Schema):
    name: str
    description: str
    total_members: int
    new_members_this_week: int
    total_articles: int
    new_articles_this_week: int
    articles_published: int
    new_published_articles_this_week: int
    total_reviews: int
    total_discussions: int
    member_growth: List[DateCount]
    article_submission_trends: List[DateCount]
    recently_published_articles: List[ArticleBasicOut]


"""
Community Article schemas for serialization and validation.
"""


class StatusFilter(str, Enum):
    SUBMITTED = "submitted"
    APPROVED_BY_ADMIN = "approved"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PUBLISHED = "published"
    UNSUBMITTED = "unsubmitted"


class CommunityArticlePseudonymousOut(Schema):
    is_pseudonymous: bool
