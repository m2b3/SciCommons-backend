# api.py
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest
from ninja import Query, Router
from django_ratelimit.decorators import ratelimit

from articles.models import Reaction
from posts.models import Comment, Post
from posts.schemas import (
    CommentCreateSchema,
    CommentOut,
    CommentUpdateSchema,
    Message,
    PaginatedPostsResponse,
    PostCreateSchema,
    PostOut,
    ReactionSchema,
)
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import Hashtag, HashtagRelation, User

router = Router(tags=["Posts"])

"""
Post related endpoints
"""


@router.post("/", response={201: PostOut, 400: Message, 500: Message}, auth=JWTAuth())
def create_post(request: HttpRequest, data: PostCreateSchema):
    with transaction.atomic():
        user = request.auth
        post = Post.objects.create(author=user, title=data.title, content=data.content)

        # Create or retrieve hashtags and create relations
        content_type = ContentType.objects.get_for_model(Post)
        for hashtag_name in data.hashtags:
            hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
            HashtagRelation.objects.create(
                hashtag=hashtag, content_type=content_type, object_id=post.id
            )

        return 201, PostOut.resolve_post(post, user)


@router.get(
    "/", response={200: PaginatedPostsResponse, 400: Message}, auth=OptionalJWTAuth
)
@ratelimit(key="user_or_ip", rate="5/m", method=ratelimit.ALL, block=True)
def list_posts(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at", enum=["created_at", "title", "upvotes"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    hashtag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    user: Optional[User] = None if not request.auth else request.auth
    posts = Post.objects.filter(is_deleted=False)

    # Apply search
    if search:
        posts = posts.filter(Q(title__icontains=search) | Q(content__icontains=search))

    # Apply hashtag filtering
    if hashtag:
        posts = posts.filter(
            id__in=HashtagRelation.objects.filter(
                hashtag__name=hashtag,
                content_type=ContentType.objects.get_for_model(Post),
            ).values_list("object_id", flat=True)
        )

    # Apply sorting
    order_prefix = "-" if sort_order == "desc" else ""
    posts = posts.order_by(f"{order_prefix}{sort_by}")

    paginator = Paginator(posts, per_page)
    page_obj = paginator.get_page(page)
    return PaginatedPostsResponse(
        items=[PostOut.resolve_post(post, user) for post in page_obj],
        total=paginator.count,
        page=page,
        per_page=per_page,
        num_pages=paginator.num_pages,
    )


@router.get("/{post_id}/", response={200: PostOut, 404: Message}, auth=OptionalJWTAuth)
def get_post(request, post_id: int):
    current_user: Optional[User] = None if not request.auth else request.auth
    post = Post.objects.get(id=post_id)
    return PostOut.resolve_post(post, current_user)


@router.put(
    "/{post_id}", response={200: PostOut, 400: Message, 404: Message}, auth=JWTAuth()
)
def update_post(request: HttpRequest, post_id: int, data: PostCreateSchema):
    with transaction.atomic():
        user = request.auth
        post = Post.objects.get(id=post_id, author=user)

        post.title = data.title
        post.content = data.content
        post.save()

        # Update hashtags
        content_type = ContentType.objects.get_for_model(Post)
        HashtagRelation.objects.filter(
            content_type=content_type, object_id=post.id
        ).delete()
        for hashtag_name in data.hashtags:
            hashtag, created = Hashtag.objects.get_or_create(name=hashtag_name.lower())
            HashtagRelation.objects.create(
                hashtag=hashtag, content_type=content_type, object_id=post.id
            )

        return 200, PostOut.resolve_post(post, user)


@router.delete("/{post_id}/", response={204: None, 403: str, 404: str}, auth=JWTAuth())
def delete_post(request, post_id: int):
    user = request.auth
    post = Post.objects.get(id=post_id, author=user)

    # Delete hashtags and reactions associated with the post
    content_type = ContentType.objects.get_for_model(Post)
    Hashtag.objects.filter(content_type=content_type, object_id=post.id).delete()
    Reaction.objects.filter(content_type=content_type, object_id=post.id).delete()

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
