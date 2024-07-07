from datetime import datetime
from typing import List, Literal, Optional

from ninja import Field, ModelSchema, Schema

from articles.models import Review, ReviewVersion
from users.models import User

"""
Article Related Schemas for serialization and deserialization
"""


class Message(Schema):
    message: str


class Tag(Schema):
    value: str
    label: str


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


class FAQSchema(Schema):
    question: str
    answer: str


class CommunityDetailsForArticle(Schema):
    name: str
    profile_pic_url: str | None
    description: str


class ArticleDetails(Schema):
    id: int
    title: str
    abstract: str
    keywords: List[Tag]
    authors: List[Tag]
    article_image_url: str | None
    article_pdf_file_url: str | None
    submission_type: Literal["Public", "Private"]
    submitter_id: int
    slug: str
    community: CommunityDetailsForArticle | None
    status: str
    published: bool
    created_at: datetime
    updated_at: datetime
    is_submitter: bool = Field(default=False)
    faqs: List[FAQSchema] = Field(default_factory=list)


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


class CommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = None  # For nested comments


class CommentSchema(Schema):
    id: int
    review_id: int
    user_id: int
    content: str
    parent_id: Optional[int] = None
    created_at: datetime = Field(..., alias="created_at")
    updated_at: datetime = Field(..., alias="updated_at")
    replies: Optional[List["CommentSchema"]] = None  # Recursive definition

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


CommentSchema.model_rebuild()


class PaginatedCommentsSchema(Schema):
    total: int
    page: int
    size: int
    comments: List[CommentSchema]


class CommentUpdateSchema(Schema):
    content: Optional[str] = None


class DeleteResponseSchema(Schema):
    success: bool
    message: str
