# api.py
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.http import HttpRequest
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Reaction
from posts.models import Comment, Post
from posts.schemas import (
    CommentCreateSchema,
    CommentOut,
    CommentUpdateSchema,
    Message,
    PostOut,
    PostSchema,
    ReactionSchema,
)
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Posts"])

"""
Post related endpoints
"""


@router.post(
    "/", response={200: PostOut, codes_4xx: Message, codes_5xx: Message}, auth=JWTAuth()
)
def create_post(request: HttpRequest, data: PostSchema):
    user = request.auth
    post = Post.objects.create(author=user, title=data.title, content=data.content)
    return post


@router.get("/", response={200: list[PostOut], codes_5xx: Message})
def list_posts(request, page: int = 1, per_page: int = 10):
    posts = Post.objects.filter(is_deleted=False).order_by("-created_at")
    paginator = Paginator(posts, per_page)
    paginated_posts = paginator.get_page(page)

    post_list = []
    for post in paginated_posts.object_list:
        upvotes = post.reactions.filter(vote=1).count()
        comments_count = Comment.objects.filter(post=post).count()
        post_out = PostOut.from_orm(post)
        post_out.upvotes = upvotes
        post_out.comments_count = comments_count
        post_list.append(post_out)

    return post_list


@router.get("/{post_id}/", response={200: PostOut, 404: Message})
def get_post(request, post_id: int):
    post = Post.objects.get(id=post_id)
    upvotes = post.reactions.filter(vote=1).count()
    post_out = PostOut.from_orm(post)
    post_out.upvotes = upvotes
    comments_count = Comment.objects.filter(post=post).count()
    post_out.comments_count = comments_count
    return post_out


@router.put("/{post_id}/", response={200: PostOut, 403: Message}, auth=JWTAuth())
def update_post(request, post_id: int, data: PostSchema):
    user = request.auth
    post = Post.objects.get(id=post_id)

    if post.author != user:
        return 403, {"message": "You are not the author of this post"}

    post.title = data.title
    post.content = data.content
    post.save()
    return post


@router.delete("/{post_id}/", response={204: None, 403: str, 404: str}, auth=JWTAuth())
def delete_post(request, post_id: int):
    user = request.auth
    post = Post.objects.get(id=post_id)

    if post.author != user:
        return 403, "You are not authorized to delete this post"

    post.content = "[deleted]"
    post.is_deleted = True
    post.save()
    return 204, None


@router.get("/{post_id}/comments/", response=List[CommentOut], auth=OptionalJWTAuth)
def list_post_comments(request, post_id: int):
    post = Post.objects.get(id=post_id)
    comments = (
        Comment.objects.filter(post=post, parent=None)
        .select_related("author")
        .order_by("created_at")
    )
    current_user: Optional[User] = None if not request.auth else request.auth
    return [
        CommentOut.from_orm_with_replies(comment, current_user) for comment in comments
    ]


@router.post(
    "/{post_id}/reactions/",
    response={200: ReactionSchema, 404: Message},
    auth=JWTAuth(),
)
def react_to_post(request: HttpRequest, post_id: int, data: ReactionSchema):
    user = request.auth
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return 404, {"message": "Post not found"}

    content_type = ContentType.objects.get_for_model(Post)

    reaction, created = Reaction.objects.update_or_create(
        user=user,
        content_type=content_type,
        object_id=post.id,
        defaults={"vote": data.vote},
    )
    return {"vote": reaction.vote}


"""
Comments related endpoints
"""


@router.post("/{post_id}/comments/", response={201: CommentOut}, auth=JWTAuth())
def create_comment(request, post_id: int, payload: CommentCreateSchema):
    user = request.auth

    post = Post.objects.get(id=post_id)
    parent_comment = None

    if payload.parent_id:
        parent_comment = Comment.objects.get(id=payload.parent_id)

    comment = Comment.objects.create(
        post=post,
        author=user,
        content=payload.content,
        parent=parent_comment,
    )
    # Return comment with replies
    return 201, CommentOut.from_orm_with_replies(comment, user)


@router.put(
    "/comments/{comment_id}/", response={200: Message, 403: Message}, auth=JWTAuth()
)
def update_comment(request, comment_id: int, payload: CommentUpdateSchema):
    comment = Comment.objects.get(id=comment_id)

    if comment.author != request.auth:
        return 403, {"message": "You do not have permission to update this comment."}

    if payload.content is not None:
        comment.content = payload.content

    comment.save()

    return 200, {"message": "Comment updated successfully"}


@router.delete(
    "/comments/{comment_id}/", response={204: None, 403: Message}, auth=JWTAuth()
)
def delete_comment(request, comment_id: int):
    user = request.auth
    comment = Comment.objects.get(id=comment_id)

    # Check if the user is the owner of the comment or has permission to delete it
    if comment.author != user:
        return 403, {"message": "You do not have permission to delete this comment."}

    # Delete reactions associated with the comment
    Reaction.objects.filter(
        content_type__model="comment", object_id=comment.id
    ).delete()

    # Logically delete the comment by clearing its content and marking it as deleted
    comment.content = "[deleted]"
    comment.is_deleted = True
    comment.save()

    return 204, None


@router.post(
    "/comments/{comment_id}/reactions/",
    response={200: ReactionSchema, 404: Message},
    auth=JWTAuth(),
)
def react_to_comment(request: HttpRequest, comment_id: int, data: ReactionSchema):
    user = request.auth
    try:
        comment = Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        return 404, {"message": "Comment not found"}

    content_type = ContentType.objects.get_for_model(Comment)

    reaction, created = Reaction.objects.update_or_create(
        user=user,
        content_type=content_type,
        object_id=comment.id,
        defaults={"vote": data.vote},
    )
    return {"vote": reaction.vote}
