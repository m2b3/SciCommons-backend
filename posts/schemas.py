from typing import List, Literal, Optional

from django.contrib.contenttypes.models import ContentType
from ninja import Field, ModelSchema, Schema

from posts.models import Comment, Post
from users.models import HashtagRelation, User


class UserOut(Schema):
    id: int
    username: str
    profile_pic_url: str | None


class PostCreateSchema(Schema):
    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)


class PostOut(ModelSchema):
    author: UserOut
    upvotes: int = Field(0)
    comments_count: int = Field(0)
    hashtags: List[str] = Field(default_factory=list)
    is_author: bool = Field(False)

    class Config:
        model = Post
        model_fields = ["id", "title", "content", "created_at"]

    @staticmethod
    def resolve_post(post: Post, current_user: Optional[User]):
        return {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "created_at": post.created_at,
            "author": UserOut.from_orm(post.author),
            "upvotes": post.reactions.filter(vote=1).count(),
            "comments_count": Comment.objects.filter(post=post).count(),
            "hashtags": [
                relation.hashtag.name
                for relation in HashtagRelation.objects.filter(
                    content_type=ContentType.objects.get_for_model(Post),
                    object_id=post.id,
                )
            ],
            "is_author": current_user == post.author if current_user else False,
        }


# Todo: Create Generic Model for PaginatedResponse
class PaginatedPostsResponse(Schema):
    items: List[PostOut]
    total: int
    page: int
    size: int


class Message(Schema):
    message: str


class CommentOut(ModelSchema):
    author: UserOut
    replies: list["CommentOut"] = Field(...)
    upvotes: int
    is_author: bool = Field(False)

    class Config:
        model = Comment
        model_fields = ["id", "content", "created_at"]

    @staticmethod
    def from_orm_with_replies(comment: Comment, current_user: Optional[User]):
        return CommentOut(
            id=comment.id,
            author=UserOut.from_orm(comment.author),
            content=comment.content,
            created_at=comment.created_at,
            upvotes=comment.reactions.filter(vote=1).count(),
            replies=[
                CommentOut.from_orm_with_replies(reply, current_user)
                for reply in comment.replies.all()
            ],
            is_author=(comment.author == current_user) if current_user else False,
        )


class CommentCreateSchema(Schema):
    content: str
    parent_id: Optional[int] = Field(
        None, description="ID of the parent comment if it's a reply"
    )


class CommentUpdateSchema(Schema):
    content: str | None


class ReactionSchema(Schema):
    vote: Literal[-1, 1]
