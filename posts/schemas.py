from typing import Literal, Optional

from ninja import Field, ModelSchema, Schema

from posts.models import Comment, Post
from users.models import User


class PostSchema(Schema):
    title: str
    content: str


class UserOut(Schema):
    id: int
    username: str
    profile_pic_url: str | None


class PostOut(ModelSchema):
    author: UserOut = Field(...)
    upvotes: int = Field(0)
    comments_count: int = Field(0)

    class Config:
        model = Post
        model_fields = ["id", "author", "title", "content", "created_at"]


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
