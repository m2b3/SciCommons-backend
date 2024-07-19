from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from django.contrib.contenttypes.models import ContentType
from ninja import Field, ModelSchema, Schema

from articles.models import (
    AnonymousIdentity,
    Article,
    ArticlePDF,
    Discussion,
    DiscussionComment,
    Review,
    ReviewComment,
    ReviewVersion,
)
from communities.models import Community, CommunityArticle
from myapp.schemas import UserStats
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


class CommunityArticleStatusSchema(Schema):
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


class ArticleOut(ModelSchema):
    authors: List[Tag]
    keywords: List[str]
    faqs: List[FAQSchema]
    total_reviews: int
    total_comments: int
    community_article_status: Optional[CommunityArticleStatusSchema]
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

    @staticmethod
    def from_orm_with_custom_fields(article: Article, current_user: Optional[User]):
        keywords = [
            relation.hashtag.name
            for relation in HashtagRelation.objects.filter(
                content_type=ContentType.objects.get_for_model(Article),
                object_id=article.id,
            )
        ]

        article_pdf_urls = [
            pdf.pdf_file_url.url for pdf in ArticlePDF.objects.filter(article=article)
        ]

        total_reviews = Review.objects.filter(article=article).count()
        total_comments = ReviewComment.objects.filter(review__article=article).count()
        user = UserStats.from_model(article.submitter, basic_details=True)

        community_article_status = None

        if CommunityArticle.objects.filter(article=article).exists():
            community_article = CommunityArticle.objects.get(article=article)
            community = community_article.community
            community_article_status = CommunityArticleStatusSchema(
                community=ArticleCommunityDetails.from_orm(community),
                status=community_article.status,
                submitted_at=community_article.submitted_at,
                published_at=community_article.published_at,
            )

        return ArticleOut(
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
            keywords=keywords,
            faqs=article.faqs,
            total_reviews=total_reviews,
            total_comments=total_comments,
            community_article_status=community_article_status,
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
    keywords: List[str]
    authors: List[Tag]
    article_link: Optional[str] = Field(default=None)
    submission_type: Literal["Public", "Private"]
    community_name: Optional[str] = Field(default=None)


class ArticleCreateSchema(Schema):
    payload: ArticleCreateDetails


class UpdateArticleDetails(Schema):
    title: str | None
    abstract: str | None
    keywords: List[str] | None
    authors: List[Tag] | None
    submission_type: Literal["Public", "Private"] | None
    faqs: List[FAQSchema] = []


class ArticleUpdateSchema(Schema):
    payload: UpdateArticleDetails


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
    article_id: int
    comments_count: int = Field(0)
    anonymous_name: str = Field(None)

    class Config:
        model = Review
        model_fields = [
            "id",
            "rating",
            "subject",
            "content",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

    @classmethod
    def from_orm(cls, review: Review, current_user: Optional[User]):
        comments_count = ReviewComment.objects.filter(review=review).count()
        versions = [
            ReviewVersionSchema.from_orm(version) for version in review.versions.all()
        ]
        anonymous_name = AnonymousIdentity.objects.get(
            article=review.article, user=review.user
        ).fake_name
        user = UserStats.from_model(review.user, basic_details=True)

        return cls(
            id=review.id,
            user=user,
            article_id=review.article.id,
            rating=review.rating,
            subject=review.subject,
            content=review.content,
            version=review.version,
            created_at=review.created_at,
            updated_at=review.updated_at,
            deleted_at=review.deleted_at,
            comments_count=comments_count,
            is_author=review.user == current_user,
            versions=versions,
            anonymous_name=anonymous_name,
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
    anonymous_name: str = Field(None)

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
        anonymous_name = AnonymousIdentity.objects.get(
            article=comment.review.article, user=comment.author
        ).fake_name

        return ReviewCommentOut(
            id=comment.id,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            anonymous_name=anonymous_name,
            is_author=(comment.author == current_user) if current_user else False,
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


"""
Discussion Related Schemas for serialization and deserialization
"""


class DiscussionOut(ModelSchema):
    is_author: bool = Field(default=False)
    user: UserStats = Field(...)
    article_id: int
    comments_count: int = Field(0)
    anonymous_name: str = Field(None)

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
        anonymous_name = AnonymousIdentity.objects.get(
            article=discussion.article, user=discussion.author
        ).fake_name
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
        anonymous_name = AnonymousIdentity.objects.get(
            article=comment.discussion.article, user=comment.author
        ).fake_name

        return ReviewCommentOut(
            id=comment.id,
            author=author,
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=replies,
            anonymous_name=anonymous_name,
            is_author=(comment.author == current_user) if current_user else False,
        )


class DiscussionCommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = Field(
        None, description="ID of the parent discussion comment if it's a reply"
    )


class DiscussionCommentUpdateSchema(Schema):
    content: str | None
