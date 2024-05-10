from typing import List, Optional

from ninja import Schema

"""
Community management schemas for serialization and validation.
"""


class CommunitySchema(Schema):
    id: int
    name: str
    description: str
    created_at: str
    slug: str
    type: str


class PaginatedCommunitySchema(Schema):
    total: int
    page: int
    size: int
    results: List[CommunitySchema]


class CommunityDetailSchema(Schema):
    id: int
    name: str
    description: str
    created_at: str
    slug: str
    type: str


class CreateCommunitySchema(Schema):
    name: str
    description: str
    type: str


class UpdateCommunitySchema(Schema):
    name: Optional[str]
    description: Optional[str]
    type: Optional[str]


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
