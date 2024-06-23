from datetime import datetime
from typing import List, Literal

from ninja import Field, Schema

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


class ReviewResponseSchema(Schema):
    id: int
    rating: int
    subject: str
    content: str
    created_at: str
    updated_at: str


class ReviewHistorySchema(Schema):
    rating: int
    subject: str
    content: str
    edited_at: datetime


class ReviewSchema(Schema):
    id: int
    article_id: int
    user_id: int
    rating: int
    subject: str
    content: str
    created_at: datetime
    updated_at: datetime
    history: List[ReviewHistorySchema]
    is_author: bool = Field(default=False)


class PaginatedReviewResponse(Schema):
    total: int
    page: int
    limit: int
    reviews: List[ReviewSchema]


class CreateReviewDetails(Schema):
    rating: int
    subject: str
    content: str
    article_id: int


class ReviewEditSchema(Schema):
    rating: int
    subject: str
    content: str


"""
Replies to Reviews Schemas for serialization and validation
"""


class ReplySchema(Schema):
    content: str
    review_id: int


class ReplyResponseSchema(Schema):
    id: int
    content: str
    review_id: int
    user_id: int
