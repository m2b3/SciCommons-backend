from enum import Enum
from typing import List, Literal, Optional

from ninja import Field, ModelSchema, Schema

from articles.models import Article, Review, ReviewComment, ReviewVersion
from users.models import User

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


class CommunityOut(Schema):
    id: int
    name: str
    description: str
    profile_pic_url: Optional[str]


class UserOut(Schema):
    id: int
    username: str
    profile_pic_url: Optional[str]


class SubmissionType(str, Enum):
    PUBLIC = "Public"
    PRIVATE = "Private"


class ArticleOut(ModelSchema):
    authors: List[Tag]
    keywords: List[Tag]
    faqs: List[FAQSchema]
    total_reviews: int
    total_comments: int
    community: Optional[CommunityOut]
    user: UserOut
    is_submitter: bool
    submission_type: SubmissionType

    class Config:
        model = Article
        model_fields = [
            "id",
            "slug",
            "title",
            "abstract",
            "article_image_url",
            "article_pdf_file_url",
            "created_at",
            "updated_at",
            "status",
            "published",
        ]

    @staticmethod
    def from_orm_with_custom_fields(article: Article, current_user: Optional[User]):
        community_data = None
        if article.community:
            community_data = CommunityOut(
                id=article.community.id,
                name=article.community.name,
                description=article.community.description,
                profile_pic_url=article.community.profile_pic_url,
            )

        return ArticleOut(
            id=article.id,
            slug=article.slug,
            title=article.title,
            abstract=article.abstract,
            article_image_url=article.article_image_url,
            article_pdf_file_url=article.article_pdf_file_url,
            created_at=article.created_at,
            updated_at=article.updated_at,
            status=article.status,
            published=article.published,
            submission_type=article.submission_type,
            authors=article.authors,
            keywords=article.keywords,
            faqs=article.faqs,
            total_reviews=Review.objects.filter(article=article).count(),
            total_comments=ReviewComment.objects.filter(
                review__article=article
            ).count(),
            community=community_data,
            user=UserOut.from_orm(article.submitter),
            is_submitter=(article.submitter == current_user) if current_user else False,
        )


# Todo: Create a Generic PaginatedResponse Schema


class PaginatedArticlesResponse(Schema):
    items: List[ArticleOut]
    total: int
    page: int
    page_size: int
    num_pages: int


class ArticleCreateDetails(Schema):
    title: str
    abstract: str
    keywords: List[Tag]
    authors: List[Tag]
    submission_type: Literal["Public", "Private"]


class ArticleCreateSchema(Schema):
    payload: ArticleCreateDetails


class ArticleResponseSchema(Schema):
    id: int
    title: str
    slug: str


class UpdateArticleDetails(Schema):
    title: str | None
    abstract: str | None
    keywords: List[Tag] | None
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


class UserOut(Schema):
    id: int
    username: str
    profile_pic_url: str | None


class ReviewSchema(ModelSchema):
    is_author: bool = Field(default=False)
    versions: List[ReviewVersionSchema] = Field(...)
    user: UserOut = Field(...)
    article_id: int
    comments_count: int = Field(0)

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
    def from_orm(cls, review: Review, current_user=Optional[User]):
        return cls(
            id=review.id,
            user=UserOut.from_orm(review.user),
            article_id=review.article.id,
            rating=review.rating,
            subject=review.subject,
            content=review.content,
            version=review.version,
            created_at=review.created_at,
            updated_at=review.updated_at,
            deleted_at=review.deleted_at,
            comments_count=ReviewComment.objects.filter(review=review).count(),
            is_author=review.user == current_user,
            versions=[
                ReviewVersionSchema.from_orm(version)
                for version in review.versions.all()
            ],
        )


class PaginatedReviewSchema(Schema):
    items: List[ReviewSchema]
    total: int
    page: int
    size: int


class ReviewResponseSchema(ModelSchema):
    class Config:
        model = Review
        model_fields = [
            "id",
            "article",
            "user",
            "rating",
            "subject",
            "content",
            "created_at",
            "updated_at",
            "version",
        ]


class ReviewUpdateSchema(ModelSchema):
    class Config:
        model = Review
        model_fields = ["rating", "subject", "content"]


"""
Comments to Reviews Schemas for serialization and validation
"""


class ReviewCommentOut(ModelSchema):
    author: UserOut
    replies: list["ReviewCommentOut"] = Field(...)
    upvotes: int
    is_author: bool = Field(False)

    class Config:
        model = ReviewComment
        model_fields = ["id", "content", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: ReviewComment, current_user: Optional[User]):
        return ReviewCommentOut(
            id=comment.id,
            author=UserOut.from_orm(comment.author),
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=[
                ReviewCommentOut.from_orm_with_replies(reply, current_user)
                # review_replies is the related name for the parent field
                for reply in comment.review_replies.all()
            ],
            is_author=(comment.author == current_user) if current_user else False,
        )


class ReviewCommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = Field(
        None, description="ID of the parent review comment if it's a reply"
    )


class ReviewCommentUpdateSchema(Schema):
    content: str | None
