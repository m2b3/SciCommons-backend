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
    ]
    submitted_at: datetime
    published_at: Optional[datetime]
    reviewer_ids: List[int] = Field(default_factory=list)
    moderator_id: Optional[int] = None

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
    def from_orm(cls, community_article: CommunityArticle):
        return cls(
            id=community_article.id,
            community=ArticleCommunityDetails.from_orm(community_article.community),
            status=community_article.status,
            submitted_at=community_article.submitted_at,
            published_at=community_article.published_at,
            reviewer_ids=list(
                community_article.assigned_reviewers.values_list("id", flat=True)
            ),
            moderator_id=(
                community_article.assigned_moderator.id
                if community_article.assigned_moderator
                else None
            ),
        )


class ArticleOut(ModelSchema):
    authors: List[Tag]
    # keywords: List[str]
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
        cls, article: Article, community: Community, current_user: Optional[User]
    ):
        # keywords = [
        #     relation.hashtag.name
        #     for relation in HashtagRelation.objects.filter(
        #         content_type=ContentType.objects.get_for_model(Article),
        #         object_id=article.id,
        #     )
        # ]

        article_pdf_urls = [
            pdf.get_url() for pdf in ArticlePDF.objects.filter(article=article)
        ]

        total_reviews = Review.objects.filter(article=article, community=community).count()
        total_ratings = Review.objects.filter(article=article, community=community).aggregate(rating=Avg("rating"))["rating"] or 0
        total_discussions = Discussion.objects.filter(article=article, community=community).count()
        total_comments = ReviewComment.objects.filter(review__article=article, review__community=community, is_deleted=False).count()
        user = UserStats.from_model(article.submitter, basic_details=True)

        community_article = None

        if CommunityArticle.objects.filter(article=article).exists():
            community_article = CommunityArticle.objects.get(article=article)
            community_article = CommunityArticleOut.from_orm(community_article)

        return cls(
            id=article.id,
            slug=article.slug,
            title=article.title,
            abstract=article.abstract,
            article_link=article.article_link,
            article_image_url=article.article_image_url,
            article_pdf_urls=article_pdf_urls,
            created_at=article.created_at,
            updated_at=article.updated_at,
            submission_type=article.submission_type,
            authors=article.authors,
            # keywords=keywords,
            faqs=article.faqs,
            total_reviews=total_reviews,
            total_discussions=total_discussions,
            total_comments=total_comments,
            community_article=community_article,
            user=user,
            is_submitter=(article.submitter == current_user) if current_user else False,
            total_ratings=total_ratings if total_ratings else 0,
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
        user = UserStats.from_model(article.submitter, basic_details=True)

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


# Todo: Create a Generic PaginatedResponse Schema


class PaginatedArticlesResponse(Schema):
    items: List[ArticleOut]
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
    anonymous_name: str = Field(None)
    avatar: str = Field(None)
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
        comments_count = ReviewComment.objects.filter(review=review, is_deleted=False).count()
        versions = [
            ReviewVersionSchema.from_orm(version) for version in review.versions.all()
        ]
        pseudonym = AnonymousIdentity.objects.get(
            article=review.article, user=review.user, community=review.community
        )
        anonymous_name = pseudonym.fake_name
        avatar = pseudonym.identicon
        user = UserStats.from_model(review.user, basic_details=True)

        community_article = None

        if CommunityArticle.objects.filter(
            article=review.article, community=review.community
        ).exists():
            community_article = CommunityArticle.objects.get(
                article=review.article, community=review.community
            )
            community_article = CommunityArticleOut.from_orm(community_article)

        comments_ratings = ReviewCommentRating.objects.filter(
                                review=review, community=review.community
                            ).exclude(
                                user=review.user
                            ).aggregate(
                                rating=Avg("rating")
                            )["rating"]

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
            anonymous_name=anonymous_name,
            avatar=avatar if avatar else None,
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
    anonymous_name: str = Field(None)
    avatar: str = Field(None)

    class Config:
        model = ReviewComment
        model_fields = ["id", "content", "rating", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: ReviewComment, current_user: Optional[User]):
        author = UserStats.from_model(comment.author, basic_details=True)
        replies = [
            ReviewCommentOut.from_orm_with_replies(reply, current_user)
            for reply in comment.review_replies.all()
        ]
        pseudonym = AnonymousIdentity.objects.get(
            article=comment.review.article, user=comment.author, community=comment.review.community
        )
        anonymous_name = pseudonym.fake_name
        avatar = pseudonym.identicon

        return ReviewCommentOut(
            id=comment.id,
            rating=comment.rating if comment.review.user != comment.author else None,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            anonymous_name=anonymous_name,
            avatar=avatar if avatar else None,
            is_author=(comment.author == current_user) if current_user else False,
            is_deleted=comment.is_deleted,
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
    anonymous_name: str = Field(None)
    avatar: str = Field(None)

    class Config:
        model = Discussion
        model_fields = [
            "id",
            "topic",
            "content",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

    @classmethod
    def from_orm(cls, discussion: Discussion, current_user: Optional[User]):
        comments_count = DiscussionComment.objects.filter(discussion=discussion).count()
        pseudonym = AnonymousIdentity.objects.get(
            article=discussion.article, user=discussion.author, community=discussion.community
        )
        anonymous_name = pseudonym.fake_name
        avatar = pseudonym.identicon
        user = UserStats.from_model(discussion.author, basic_details=True)

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
            anonymous_name=anonymous_name,
            avatar=avatar if avatar else None,
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
    anonymous_name: str = Field(None)
    avatar: str = Field(None)

    class Config:
        model = DiscussionComment
        model_fields = ["id", "content", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: DiscussionComment, current_user: Optional[User]):
        author = UserStats.from_model(comment.author, basic_details=True)
        replies = [
            DiscussionCommentOut.from_orm_with_replies(reply, current_user)
            for reply in DiscussionComment.objects.filter(parent=comment)
        ]
        pseudonym = AnonymousIdentity.objects.get(
            article=comment.discussion.article, user=comment.author, community=comment.discussion.community
        )
        anonymous_name = pseudonym.fake_name
        avatar = pseudonym.identicon

        return DiscussionCommentOut(
            id=comment.id,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            anonymous_name=anonymous_name,
            is_author=(comment.author == current_user) if current_user else False,
            avatar=avatar if avatar else None,
        )


class DiscussionCommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = Field(
        None, description="ID of the parent discussion comment if it's a reply"
    )


class DiscussionCommentUpdateSchema(Schema):
    content: str | None


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
