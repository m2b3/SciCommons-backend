from datetime import date, datetime
from enum import Enum
from typing import List, Literal, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Sum
from ninja import Field, ModelSchema, Schema

from articles.models import (
    AnonymousIdentity,
    Article,
    ArticlePDF,
    Discussion,
    DiscussionComment,
    DiscussionSubscription,
    DiscussionSummary,
    Review,
    ReviewComment,
    ReviewCommentRating,
    ReviewVersion,
)
from communities.models import Community, CommunityArticle
from myapp.schemas import DateCount, FilterType, UserStats
from users.models import HashtagRelation, User

"""
Article Related Schemas for serialization and deserialization
"""


class Message(Schema):
    message: str


class Tag(Schema):
    value: str
    label: str


class FAQSchema(Schema):
    question: str
    answer: str


class SubmissionType(str, Enum):
    PUBLIC = "Public"
    PRIVATE = "Private"


class ArticleCommunityDetails(ModelSchema):
    class Config:
        model = Community
        model_fields = ["id", "name", "description", "profile_pic_url"]


class CommunityArticleForList(Schema):
    id: int
    community: ArticleCommunityDetails

    @classmethod
    def from_orm(
        cls, community_article: CommunityArticle, current_user: Optional[User]
    ):
        community_obj = (
            ArticleCommunityDetails.from_orm(community_article.community)
            if hasattr(community_article, "community")
            else None
        )
        return cls(
            id=community_article.id,
            community=community_obj,
        )


class CommunityArticleOut(ModelSchema):
    id: int
    community: ArticleCommunityDetails
    status: Literal[
        "submitted",
        "approved",
        "under_review",
        "accepted",
        "rejected",
        "published",
        "unpublished",
    ]
    submitted_at: datetime
    published_at: Optional[datetime]
    reviewer_ids: List[int] = Field(default_factory=list)
    moderator_id: Optional[int] = None
    is_pseudonymous: bool
    is_admin: bool

    class Config:
        model = CommunityArticle
        model_fields = [
            "id",
            "community",
            "status",
            "submitted_at",
            "published_at",
        ]

    @classmethod
    def from_orm(
        cls, community_article: CommunityArticle, current_user: Optional[User]
    ):
        # Safety: ensure prefetching/optimization was done
        if (
            not hasattr(community_article, "_prefetched_objects_cache")
            or "assigned_reviewers" not in community_article._prefetched_objects_cache
        ):
            # Optional: Log warning in development
            # logger.warning("assigned_reviewers not prefetched for CommunityArticle id=%s", community_article.id)
            pass

        reviewer_ids = (
            list(community_article.assigned_reviewers.values_list("id", flat=True))
            if hasattr(community_article, "assigned_reviewers")
            else []
        )

        moderator_id = (
            community_article.assigned_moderator.id
            if community_article.assigned_moderator
            else None
        )

        community_obj = (
            ArticleCommunityDetails.from_orm(community_article.community)
            if hasattr(community_article, "community")
            else None
        )

        is_admin = (
            community_article.community.is_admin(current_user)
            if current_user and not isinstance(current_user, bool)
            else False
        )

        return cls(
            id=community_article.id,
            community=community_obj,
            status=community_article.status,
            submitted_at=community_article.submitted_at,
            published_at=community_article.published_at,
            reviewer_ids=reviewer_ids,
            moderator_id=moderator_id,
            is_pseudonymous=community_article.is_pseudonymous,
            is_admin=is_admin,
        )


class ArticlesListOut(ModelSchema):
    authors: List[Tag]
    community_article: Optional[CommunityArticleForList]
    user: UserStats
    total_ratings: float
    id: int
    slug: str
    title: str
    abstract: str
    article_image_url: Optional[str] = None
    is_bookmarked: Optional[bool] = None

    class Config:
        model = Article
        model_fields = ["id", "slug", "title", "abstract", "article_image_url"]

    @classmethod
    def from_orm_with_fields(
        cls,
        article: Article,
        total_ratings: float,
        community_article: Optional[CommunityArticle],
        is_bookmarked: Optional[bool] = None,
    ):
        return cls(
            id=article.id,
            slug=article.slug,
            title=article.title,
            abstract=article.abstract,
            authors=article.authors,
            community_article=(
                CommunityArticleForList.from_orm(community_article, None)
                if community_article
                else None
            ),
            user=UserStats.from_model(article.submitter, basic_details=True),
            article_image_url=article.article_image_url,
            total_ratings=total_ratings,
            is_bookmarked=is_bookmarked,
        )


class ArticleOut(ModelSchema):
    authors: List[Tag]
    faqs: List[FAQSchema]
    total_discussions: int
    total_reviews: int
    total_ratings: float
    total_comments: int
    community_article: Optional[CommunityArticleOut]
    article_pdf_urls: List[str]
    user: UserStats
    is_submitter: bool
    submission_type: SubmissionType
    is_pseudonymous: bool = Field(False)
    is_bookmarked: Optional[bool] = None

    class Config:
        model = Article
        model_fields = [
            "id",
            "slug",
            "title",
            "abstract",
            "article_link",
            "article_image_url",
            "created_at",
            "updated_at",
        ]

    @classmethod
    def from_orm_with_custom_fields(
        cls,
        article: Article,
        pdf_urls: List[str],
        total_reviews: int,
        total_ratings: float,
        total_discussions: int,
        total_comments: int,
        community_article: Optional[CommunityArticle],
        current_user: Optional[User],
        is_bookmarked: Optional[bool] = None,
    ):
        is_pseudonymous = False
        community_article_out = None
        if community_article:
            community_article_out = CommunityArticleOut.from_orm(
                community_article, current_user
            )
            is_pseudonymous = community_article_out.is_pseudonymous

        return cls(
            id=article.id,
            slug=article.slug,
            title=article.title,
            abstract=article.abstract,
            article_link=article.article_link,
            article_image_url=article.article_image_url,
            article_pdf_urls=pdf_urls,
            created_at=article.created_at,
            updated_at=article.updated_at,
            submission_type=article.submission_type,
            authors=article.authors,
            faqs=article.faqs,
            total_reviews=total_reviews,
            total_ratings=total_ratings,
            total_discussions=total_discussions,
            total_comments=total_comments,
            community_article=community_article_out,
            user=UserStats.from_model(
                article.submitter, basic_details_with_reputation=True
            ),
            is_submitter=(article.submitter == current_user) if current_user else False,
            is_pseudonymous=is_pseudonymous,
            is_bookmarked=is_bookmarked,
        )


class ArticleBasicOut(ModelSchema):
    total_reviews: int
    total_discussions: int
    user: UserStats
    is_submitter: bool

    class Config:
        model = Article
        model_fields = [
            "id",
            "slug",
            "title",
            "article_image_url",
        ]

    @classmethod
    def from_orm_with_custom_fields(
        cls, article: Article, current_user: Optional[User]
    ):
        total_reviews = Review.objects.filter(article=article).count()
        total_discussions = Discussion.objects.filter(article=article).count()
        user = UserStats.from_model(
            article.submitter, basic_details_with_reputation=True
        )

        return cls(
            id=article.id,
            slug=article.slug,
            title=article.title,
            article_image_url=article.article_image_url,
            total_reviews=total_reviews,
            total_discussions=total_discussions,
            user=user,
            is_submitter=(article.submitter == current_user) if current_user else False,
        )


class ArticleMetaOut(ModelSchema):
    class Config:
        model = Article
        model_fields = [
            "title",
            "abstract",
            "article_image_url",
        ]


# Todo: Create a Generic PaginatedResponse Schema


class PaginatedArticlesResponse(Schema):
    items: List[ArticleOut]
    total: int
    page: int
    per_page: int
    num_pages: int


class PaginatedArticlesListResponse(Schema):
    items: List[ArticlesListOut]
    total: int
    page: int
    per_page: int
    num_pages: int


class ArticleCreateDetails(Schema):
    title: str
    abstract: str
    # keywords: List[str]
    authors: List[Tag]
    article_link: Optional[str] = Field(default=None)
    submission_type: Literal["Public", "Private"]
    community_name: Optional[str] = Field(default=None)
    pdf_link: Optional[str] = Field(default=None)


class ArticleCreateSchema(Schema):
    payload: ArticleCreateDetails


class UpdateArticleDetails(Schema):
    title: str | None
    abstract: str | None
    # keywords: List[str] | None
    authors: List[Tag] | None
    submission_type: Literal["Public", "Private"] | None
    faqs: List[FAQSchema] = []


class ArticleUpdateSchema(Schema):
    payload: UpdateArticleDetails


class ArticleFilters(Schema):
    filter_type: FilterType
    limit: int = 10
    offset: int = 0
    community_id: Optional[int] = None


"""
Article Reviews Schemas for serialization and validation
"""


class CreateReviewSchema(Schema):
    rating: int
    subject: str
    content: str


class ReviewVersionSchema(ModelSchema):
    class Config:
        model = ReviewVersion
        model_fields = [
            "id",
            "rating",
            "subject",
            "content",
            "version",
            "created_at",
        ]


class ReviewOut(ModelSchema):
    is_author: bool = Field(default=False)
    versions: List[ReviewVersionSchema] = Field(...)
    user: UserStats = Field(...)
    community_article: Optional[CommunityArticleOut] = None
    article_id: int
    comments_count: int = Field(0)
    comments_ratings: float = Field(0)
    # anonymous_name: str = Field(None)
    # avatar: str = Field(None)
    is_pseudonymous: bool = Field(False)
    is_approved: bool = Field(False)

    class Config:
        model = Review
        model_fields = [
            "id",
            "rating",
            "review_type",
            "subject",
            "content",
            "version",
            "is_approved",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

    @classmethod
    def from_orm(cls, review: Review, current_user: Optional[User]):
        comments_count = ReviewComment.objects.filter(
            review=review, is_deleted=False
        ).count()
        versions = [
            ReviewVersionSchema.from_orm(version)
            for version in review.versions.all().order_by("-version")[:3]
        ]
        is_pseudonymous = review.is_pseudonymous
        # if is_pseudonymous:
        #     pseudonym = AnonymousIdentity.objects.get(
        #         article=review.article, user=review.user, community=review.community
        #     )
        #     anonymous_name = pseudonym.fake_name
        #     avatar = pseudonym.identicon
        # else:
        #     anonymous_name = None
        #     avatar = None
        user = UserStats.from_model(review.user, basic_details_with_reputation=True)
        if is_pseudonymous:
            pseudonym = AnonymousIdentity.objects.get(
                article=review.article, user=review.user, community=review.community
            )
            user.username = pseudonym.fake_name
            user.profile_pic_url = pseudonym.identicon

        community_article = None

        if CommunityArticle.objects.filter(
            article=review.article, community=review.community
        ).exists():
            community_article = CommunityArticle.objects.get(
                article=review.article, community=review.community
            )
            community_article = CommunityArticleOut.from_orm(
                community_article, current_user
            )

        comments_ratings = round(
            ReviewCommentRating.objects.filter(
                review=review, community=review.community
            )
            .exclude(user=review.user)
            .aggregate(rating=Avg("rating"))["rating"]
            or 0,
            1,
        )

        return cls(
            id=review.id,
            user=user,
            article_id=review.article.id,
            rating=review.rating,
            review_type=review.review_type,
            subject=review.subject,
            content=review.content,
            version=review.version,
            created_at=review.created_at,
            updated_at=review.updated_at,
            deleted_at=review.deleted_at,
            comments_count=comments_count,
            is_author=review.user == current_user,
            is_approved=review.is_approved,
            versions=versions,
            # anonymous_name=anonymous_name,
            # avatar=avatar if avatar else None,
            is_pseudonymous=is_pseudonymous,
            community_article=community_article,
            comments_ratings=comments_ratings if comments_ratings else 0,
        )


class PaginatedReviewSchema(Schema):
    items: List[ReviewOut]
    total: int
    page: int
    size: int


class ReviewUpdateSchema(Schema):
    rating: int | None
    subject: str | None
    content: str | None


"""
Comments to Reviews Schemas for serialization and validation
"""


class ReviewCommentOut(ModelSchema):
    author: UserStats
    replies: list["ReviewCommentOut"] = Field(...)
    upvotes: int
    is_author: bool = Field(False)
    is_deleted: bool = Field(False)
    # anonymous_name: str = Field(None)
    # avatar: str = Field(None)
    is_pseudonymous: bool = Field(False)

    class Config:
        model = ReviewComment
        model_fields = ["id", "content", "rating", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: ReviewComment, current_user: Optional[User]):
        author = UserStats.from_model(
            comment.author, basic_details_with_reputation=True
        )
        replies = [
            ReviewCommentOut.from_orm_with_replies(reply, current_user)
            for reply in comment.review_replies.all()
        ]
        is_pseudonymous = comment.is_pseudonymous
        # if is_pseudonymous:
        #     pseudonym = AnonymousIdentity.objects.get(
        #         article=comment.review.article, user=comment.author, community=comment.review.community
        #     )
        #     anonymous_name = pseudonym.fake_name
        #     avatar = pseudonym.identicon
        # else:
        #     anonymous_name = None
        #     avatar = None
        if is_pseudonymous:
            pseudonym = AnonymousIdentity.objects.get(
                article=comment.review.article,
                user=comment.author,
                community=comment.review.community,
            )
            author.username = pseudonym.fake_name
            author.profile_pic_url = pseudonym.identicon

        return ReviewCommentOut(
            id=comment.id,
            rating=comment.rating if comment.review.user != comment.author else None,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            # anonymous_name=anonymous_name,
            # avatar=avatar if avatar else None,
            is_author=(comment.author == current_user) if current_user else False,
            is_deleted=comment.is_deleted,
            is_pseudonymous=is_pseudonymous,
        )


class ReviewCommentCreateSchema(Schema):
    content: str
    rating: int
    parent_id: Optional[int] = Field(
        None, description="ID of the parent review comment if it's a reply"
    )


class ReviewCommentUpdateSchema(Schema):
    content: str | None
    rating: int | None


class ReviewCommentRatingByUserOut(Schema):
    rating: int | None


"""
Discussion Related Schemas for serialization and deserialization
"""


class DiscussionOut(ModelSchema):
    is_author: bool = Field(default=False)
    user: UserStats = Field(...)
    article_id: int
    comments_count: int = Field(0)
    # anonymous_name: str = Field(None)
    # avatar: str = Field(None)
    is_pseudonymous: bool = Field(False)
    is_resolved: bool = Field(False)

    class Config:
        model = Discussion
        model_fields = [
            "id",
            "topic",
            "content",
            "created_at",
            "updated_at",
            "deleted_at",
            "is_resolved",
        ]

    @classmethod
    def from_orm(cls, discussion: Discussion, current_user: Optional[User]):
        comments_count = DiscussionComment.objects.filter(discussion=discussion).count()
        is_pseudonymous = discussion.is_pseudonymous
        # if is_pseudonymous:
        #     pseudonym = AnonymousIdentity.objects.get(
        #         article=discussion.article, user=discussion.author, community=discussion.community
        #     )
        #     anonymous_name = pseudonym.fake_name
        #     avatar = pseudonym.identicon
        # else:
        #     anonymous_name = None
        #     avatar = None
        user = UserStats.from_model(
            discussion.author, basic_details_with_reputation=True
        )
        if is_pseudonymous:
            pseudonym = AnonymousIdentity.objects.get(
                article=discussion.article,
                user=discussion.author,
                community=discussion.community,
            )
            user.username = pseudonym.fake_name
            user.profile_pic_url = pseudonym.identicon

        return cls(
            id=discussion.id,
            user=user,
            topic=discussion.topic,
            article_id=discussion.article.id,
            content=discussion.content,
            created_at=discussion.created_at,
            updated_at=discussion.updated_at,
            deleted_at=discussion.deleted_at,
            comments_count=comments_count,
            is_author=discussion.author == current_user,
            # anonymous_name=anonymous_name,
            # avatar=avatar if avatar else None,
            is_pseudonymous=is_pseudonymous,
            is_resolved=discussion.is_resolved,
        )


class CreateDiscussionSchema(Schema):
    topic: str
    content: str


class PaginatedDiscussionSchema(Schema):
    items: List[DiscussionOut]
    total: int
    page: int
    per_page: int


"""
Discussion Comments Schemas for serialization and validation
"""


class DiscussionCommentOut(ModelSchema):
    author: UserStats
    replies: list["DiscussionCommentOut"] = Field(...)
    upvotes: int
    is_author: bool = Field(False)
    # anonymous_name: str = Field(None)
    # avatar: str = Field(None)
    is_pseudonymous: bool = Field(False)

    class Config:
        model = DiscussionComment
        model_fields = ["id", "content", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: DiscussionComment, current_user: Optional[User]):
        author = UserStats.from_model(
            comment.author, basic_details_with_reputation=True
        )
        replies = [
            DiscussionCommentOut.from_orm_with_replies(reply, current_user)
            for reply in DiscussionComment.objects.filter(parent=comment)
        ]
        # pseudonym = AnonymousIdentity.objects.get(
        #     article=comment.discussion.article, user=comment.author, community=comment.discussion.community
        # )
        # anonymous_name = pseudonym.fake_name
        # avatar = pseudonym.identicon
        is_pseudonymous = comment.is_pseudonymous
        if is_pseudonymous:
            pseudonym = AnonymousIdentity.objects.get(
                article=comment.discussion.article,
                user=comment.author,
                community=comment.discussion.community,
            )
            author.username = pseudonym.fake_name
            author.profile_pic_url = pseudonym.identicon

        return DiscussionCommentOut(
            id=comment.id,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            # anonymous_name=anonymous_name,
            is_author=(comment.author == current_user) if current_user else False,
            # avatar=avatar if avatar else None,
            is_pseudonymous=is_pseudonymous,
        )


class DiscussionCommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = Field(
        None, description="ID of the parent discussion comment if it's a reply"
    )


class DiscussionCommentUpdateSchema(Schema):
    content: str | None


class DiscussionSubscriptionSchema(Schema):
    community_article_id: int
    community_id: int


class DiscussionSubscriptionOut(ModelSchema):
    community_article_id: int
    community_id: int
    article_id: int
    subscribed_at: datetime
    is_active: bool

    class Config:
        model = DiscussionSubscription
        model_fields = [
            "id",
            "subscribed_at",
            "is_active",
        ]

    @classmethod
    def from_orm(cls, subscription):
        return cls(
            id=subscription.id,
            community_article_id=subscription.community_article.id,
            community_id=subscription.community.id,
            article_id=subscription.article.id,
            subscribed_at=subscription.subscribed_at,
            is_active=subscription.is_active,
        )


class DiscussionSubscriptionUpdateSchema(Schema):
    is_active: bool | None = None


class SubscriptionStatusSchema(Schema):
    is_subscribed: bool
    subscription: Optional[DiscussionSubscriptionOut] = None


class SubscriptionArticleOut(Schema):
    article_id: int
    article_title: str
    article_slug: str
    article_abstract: str
    community_article_id: int


class CommunitySubscriptionOut(Schema):
    community_id: int
    community_name: str
    is_admin: bool
    articles: List[SubscriptionArticleOut]


class UserSubscriptionsOut(Schema):
    communities: List[CommunitySubscriptionOut]


"""
Article Stats Related Schemas for serialization and deserialization
"""


class ReviewExcerpt(Schema):
    excerpt: str
    date: datetime


class OfficialArticleStatsResponse(Schema):
    title: str
    submission_date: date
    submitter: str
    discussions: int
    likes: int
    reviews_count: int
    recent_reviews: List[ReviewExcerpt]
    reviews_over_time: List[DateCount]
    likes_over_time: List[DateCount]
    average_rating: float


class CommunityArticleStatsResponse(Schema):
    title: str
    submission_date: datetime
    submitter: str
    community_name: Optional[str]
    discussions: int
    likes: int
    reviews_count: int
    recent_reviews: List[ReviewExcerpt]
    reviews_over_time: List[DateCount]
    likes_over_time: List[DateCount]
    average_rating: float


"""
Discussion Summary Schemas for serialization and validation
"""


class DiscussionSummaryOut(ModelSchema):
    created_by: Optional[UserStats] = None
    last_updated_by: Optional[UserStats] = None

    class Config:
        model = DiscussionSummary
        model_fields = [
            "id",
            "content",
            "created_at",
            "updated_at",
        ]

    @classmethod
    def from_orm(cls, summary: DiscussionSummary):
        created_by = None
        last_updated_by = None

        if summary.created_by_id and hasattr(summary, "created_by"):
            created_by = UserStats.from_model(summary.created_by, basic_details=True)

        if summary.last_updated_by_id and hasattr(summary, "last_updated_by"):
            last_updated_by = UserStats.from_model(
                summary.last_updated_by, basic_details=True
            )

        return cls(
            id=summary.id,
            content=summary.content,
            created_by=created_by,
            last_updated_by=last_updated_by,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


class DiscussionSummaryCreateSchema(Schema):
    content: str


class DiscussionSummaryUpdateSchema(Schema):
    content: str
