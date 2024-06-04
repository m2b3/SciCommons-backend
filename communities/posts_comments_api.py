from typing import List

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Router

from communities.models import Community, CommunityComment, CommunityPost
from communities.schemas import (
    CommentIn,
    CommunityPostDetailOut,
    CommunityPostOut,
    CreatePostSchema,
    UpdatePostSchema,
)
from users.auth import JWTAuth

# Initialize a router for the communities API
router = Router(auth=JWTAuth(), tags=["CommunitiesPosts"])


# Endpoint for getting all posts in a community
@router.get("/{community_id}/posts/", response=List[CommunityPostOut])
def list_community_posts(request, community_id: int):
    try:
        # Retrieve the specified community or raise a 404 error if not found
        community = get_object_or_404(Community, pk=community_id)

        # Check visibility and user membership for access control
        if (
            community.type == "public"
            or (community.type == "hidden" and request.auth in community.members.all())
            or (community.type == "locked" and request.auth in community.members.all())
        ):
            posts = CommunityPost.objects.filter(community=community).order_by(
                "-created_at"
            )
            return posts

        # Unauthorized access due to restricted community
        return {
            "detail": "Access denied. You do not have "
            "permission to view this community's posts."
        }, 403

    except Http404:
        # Handle case when the community is not found
        return {"detail": f"Community with ID {community_id} does not exist."}, 404

    except Exception as e:
        # Catch any other unexpected errors and respond accordingly
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


# Endpoint for getting a specific post by its ID
@router.get("/posts/{post_id}/", response=CommunityPostDetailOut)
def retrieve_post(request, post_id: int):
    try:
        # Retrieve the specified post or raise a 404 error if not found
        post = get_object_or_404(CommunityPost, pk=post_id)
        community = post.community

        # Check visibility and user membership for access control
        if (
            community.type == "public"
            or (community.type == "hidden" and request.auth in community.members.all())
            or (community.type == "locked" and request.auth in community.members.all())
        ):
            return post

        # Unauthorized access due to restricted community
        return {
            "detail": "Access denied. You do not have permission to view this post."
        }, 403

    except Http404:
        # Handle case when the post is not found
        return {"detail": f"Post with ID {post_id} does not exist."}, 404

    except Exception as e:
        # Catch any other unexpected errors and respond accordingly
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.post("/{community_id}/posts/")
def create_community_post(request, community_id: int, payload: CreatePostSchema):
    try:
        # Retrieve the community, returning 404 if it does not exist
        community = get_object_or_404(Community, pk=community_id)

        # Check that the user has permission to post in this community
        if (
            community.type == "public"
            or (community.type == "hidden" and request.auth in community.members.all())
            or (community.type == "locked" and request.auth in community.members.all())
        ):

            # Create a new post using the data from the request payload
            new_post = CommunityPost(
                community=community,
                title=payload.title,
                content=payload.content,
                author=request.auth,
                cited_article_id=(
                    payload.cited_article_id if payload.cited_article_id else None
                ),
                cited_url=payload.cited_url if payload.cited_url else "",
            )
            new_post.save()

            return {"message": "Post created successfully", "post_id": new_post.id}

        # Access denied due to restricted community type
        return (
            {
                "detail": "Access denied. You do not have permission \
                to post in this community."
            },
            403,
        )

    except Http404:
        # Handle case where the community was not found
        return {"detail": f"Community with ID {community_id} does not exist."}, 404

    except Exception as e:
        # Catch any unexpected errors and provide an appropriate error response
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.put("/posts/{post_id}/")
@router.patch("/posts/{post_id}/")
def update_community_post(request, post_id: int, payload: UpdatePostSchema):
    try:
        # Retrieve the post or raise a 404 error if not found
        post = get_object_or_404(CommunityPost, pk=post_id)
        community = post.community

        # Determine if the requester is the author or a community admin/moderator
        is_author = request.auth == post.author
        is_admin_or_moderator = (
            request.auth in community.admins.all()
            or request.auth in community.moderators.all()
        )

        if not (is_author or is_admin_or_moderator):
            return (
                {
                    "detail": "Permission denied. Only the post author or \
                    community admins/moderators can edit this post."
                },
                403,
            )

        # Update the post's fields if provided in the payload
        if payload.title:
            post.title = payload.title
        if payload.content:
            post.content = payload.content
        if payload.cited_article_id is not None:
            post.cited_article_id = payload.cited_article_id
        if payload.cited_url:
            post.cited_url = payload.cited_url

        post.save()

        return {"message": "Post updated successfully", "post_id": post.id}

    except Http404:
        # Handle case where the post is not found
        return {"detail": f"Post with ID {post_id} does not exist."}, 404

    except Exception as e:
        # Catch unexpected errors and provide an appropriate error response
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.delete("/posts/{post_id}/", response={204: None})
def delete_community_post(request, post_id: int):
    try:
        # Retrieve the post or raise a 404 error if not found
        post = get_object_or_404(CommunityPost, pk=post_id)
        community = post.community

        # Check if the user is a moderator or admin in the community
        if (
            request.auth in community.moderators.all()
            or request.auth in community.admins.all()
        ):
            post.delete()
            return HttpResponse(
                status=204
            )  # No content to indicate successful deletion

        # Return permission denied if the user is not a moderator or admin
        return (
            {
                "detail": "Permission denied. Only community moderators \
                or admins can delete posts."
            },
            403,
        )

    except Http404:
        # Handle the case where the post is not found
        return {"detail": f"Post with ID {post_id} does not exist."}, 404

    except Exception as e:
        # Catch any other unexpected errors and provide an appropriate error response
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.post("/posts/{post_id}/comments/")
def add_comment_to_post(request, post_id: int, payload: CommentIn):
    try:
        # Retrieve the post or raise a 404 error if not found
        post = get_object_or_404(CommunityPost, pk=post_id)

        # Check if the user has permission to comment (public/hidden/locked)
        if (
            post.community.type == "public"
            or (
                post.community.type == "hidden"
                and request.auth in post.community.members.all()
            )
            or (
                post.community.type == "locked"
                and request.auth in post.community.members.all()
            )
        ):
            # Create and save the new comment
            comment = CommunityComment.objects.create(
                post=post, author=request.auth, content=payload.content
            )
            return {"detail": "Comment added successfully.", "id": comment.id}, 201

        # Unauthorized access due to restricted community
        return {
            "detail": "Access denied. You do not have permission"
            " to comment on this post."
        }, 403

    except ValidationError as e:
        # Handle validation errors
        return {"detail": str(e)}, 400

    except Http404:
        # Handle the case when the post is not found
        return {"detail": f"Post with ID {post_id} does not exist."}, 404

    except Exception as e:
        # Catch any other unexpected errors
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.patch(
    "/comments/{comment_id}/",
    response={200: str, 400: str, 403: str, 404: str, 500: str},
)
def update_comment(request, comment_id: int, payload: CommentIn):
    try:
        # Retrieve the specific comment or raise a 404 error if not found
        comment = get_object_or_404(CommunityComment, pk=comment_id)

        # Check if the user is the author of the comment or a moderator of the community
        is_author = request.auth == comment.author
        is_moderator = request.auth in comment.post.community.moderators.all()

        if is_author or is_moderator:
            # Update the content of the comment
            comment.content = payload.content
            comment.save()
            return {"detail": "Comment updated successfully."}, 200

        # Unauthorized access if the user is not the author or a moderator
        return {
            "detail": "Access denied. You do not have permission to edit this comment."
        }, 403

    except ValidationError as e:
        # Handle validation errors
        return {"detail": str(e)}, 400

    except Http404:
        # Handle the case when the comment is not found
        return {"detail": f"Comment with ID {comment_id} does not exist."}, 404

    except Exception as e:
        # Catch unexpected errors and provide a generalized error response
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500


@router.delete(
    "/comments/{comment_id}/",
    response={200: str, 400: str, 403: str, 404: str, 500: str},
)
def delete_comment(request, comment_id: int):
    try:
        # Retrieve the comment or raise a 404 error if not found
        comment = get_object_or_404(CommunityComment, pk=comment_id)

        # Check if the user is the author or a moderator of the community
        is_author = request.auth == comment.author
        is_moderator = request.auth in comment.post.community.moderators.all()

        if is_author or is_moderator:
            # Delete the comment
            comment.delete()
            return {"detail": "Comment deleted successfully."}, 200

        # Unauthorized access if the user is not the author or a moderator
        return (
            {
                "detail": "Access denied. You do not have permission  \
                to delete this comment."
            },
            403,
        )

    except ValidationError as e:
        # Handle validation errors
        return {"detail": str(e)}, 400

    except Http404:
        # Handle the case when the comment is not found
        return {"detail": f"Comment with ID {comment_id} does not exist."}, 404

    except Exception as e:
        # Catch any unexpected errors and provide a generalized error response
        return {"detail": f"An unexpected error occurred: {str(e)}"}, 500
