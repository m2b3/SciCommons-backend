from typing import List, Optional

from ninja import Schema


class ArticleCreateSchema(Schema):
    title: str
    abstract: str
    keywords: str
    authors: str
    submission_type: str


class ArticleResponseSchema(Schema):
    id: int
    title: str
    slug: str


class ReviewSchema(Schema):
    id: int
    user: int
    rating: int
    subject: str
    content: str
    created_at: str
    updated_at: str


class PaginatedReviewSchema(Schema):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[ReviewSchema]


class ArticleSchema(Schema):
    id: int
    title: str
    abstract: str
    keywords: str
    authors: str
    image: Optional[str] = None
    pdf_file: Optional[str] = None
    submission_type: str
    submitter: int
    slug: str
    reviews: PaginatedReviewSchema


class ReviewSchema(Schema):
    rating: int
    subject: str
    content: str
    article_id: int


class ReviewResponseSchema(Schema):
    id: int
    rating: int
    subject: str
    content: str
    created_at: str
    updated_at: str


class ArticleReviewsResponseSchema(Schema):
    count: int
    next: Optional[int]
    previous: Optional[int]
    results: List[ReviewResponseSchema]


class ReviewEditSchema(Schema):
    rating: int
    subject: str
    content: str


class ReplySchema(Schema):
    content: str
    review_id: int


class ReplyResponseSchema(Schema):
    id: int
    content: str
    review_id: int
    user_id: int
