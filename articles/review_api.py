from typing import List, Optional

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import (
    Article,
    Reaction,
    Review,
    ReviewComment,
    ReviewCommentRating,
)
from articles.schemas import (
    CreateReviewSchema,
    Message,
    PaginatedReviewSchema,
    ReviewCommentCreateSchema,
    ReviewCommentOut,
    ReviewCommentRatingByUserOut,
    ReviewCommentUpdateSchema,
    ReviewOut,
    ReviewUpdateSchema,
)
from communities.models import Community, CommunityArticle
from myapp.feature_flags import MAX_NESTING_LEVEL
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Reviews"])


@router.post(
    "/{article_id}/reviews/",
    response={201: ReviewOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_review(
    request,
    article_id: int,
    review_data: CreateReviewSchema,
    community_id: Optional[int] = None,
):
    try:
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        user = request.auth

        # Uncomment this after testing
        # if article.submitter == user:
        #     return 400, {"message": "You can't review your own article."}

        try:
            existing_review = Review.objects.filter(article=article, user=user)
        except Exception:
            return 500, {
                "message": "Error checking existing reviews. Please try again."
            }

        is_pseudonymous = False
        community = None
        community_article = None

        if community_id:
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            except Exception:
                return 500, {"message": "Error retrieving community. Please try again."}

            if not community.is_member(user):
                return 403, {"message": "You are not a member of this community."}

            try:
                community_article = CommunityArticle.objects.get(
                    article=article, community=community
                )
            except CommunityArticle.DoesNotExist:
                return 404, {"message": "Article not found in this community."}
            except Exception:
                return 500, {
                    "message": "Error retrieving community article. Please try again."
                }

            # Future implementation code commented out
            # if community_article.assigned_reviewers.filter(id=user.id).exists():
            #     review_type = Review.REVIEWER
            # elif community_article.assigned_moderator == user:
            #     review_type = Review.MODERATOR
            # else:
            #     review_type = Review.PUBLIC

            # if review_type == Review.PUBLIC:
            #     if community_article.status != CommunityArticle.ACCEPTED:
            #         return 403, {"message": "This article is not currently accepted."}
            # elif review_type == Review.REVIEWER:
            #     if community_article.status != CommunityArticle.UNDER_REVIEW:
            #         return 403, {"message": "This article is not currently under review."}
            # elif review_type == Review.MODERATOR:
            #     if community_article.status != CommunityArticle.UNDER_REVIEW:
            #         return 403, {"message": "This article is not currently under review."}

            #     assigned_reviewer_count = community_article.assigned_reviewers.count()
            #     if assigned_reviewer_count > 0:
            #         approved_review_count = Review.objects.filter(
            #             community_article=community_article,
            #             user__in=community_article.assigned_reviewers.all(),
            #             is_approved=True,
            #         ).count()

            #         if approved_review_count < assigned_reviewer_count:
            #             return 403, {
            #                 "message": "You can only review this article "
            #                 "after all assigned reviewers have approved it."
            #             }

            review_type = Review.PUBLIC
            if community_article.is_pseudonymous:
                is_pseudonymous = True

            try:
                if existing_review.filter(community=community).exists():
                    return 400, {
                        "message": "You have already reviewed this article in this community."
                    }
            except Exception:
                return 500, {
                    "message": "Error checking existing reviews. Please try again."
                }

        else:
            try:
                if existing_review.filter(community__isnull=True).exists():
                    return 400, {"message": "You have already reviewed this article."}
            except Exception:
                return 500, {
                    "message": "Error checking existing reviews. Please try again."
                }

            review_type = Review.PUBLIC

        try:
            review = Review.objects.create(
                article=article,
                user=user,
                community=community,
                community_article=community_article,
                review_type=review_type,
                rating=review_data.rating,
                subject=review_data.subject,
                content=review_data.content,
                is_pseudonymous=is_pseudonymous,
            )
        except Exception:
            return 500, {"message": "Error creating review. Please try again."}

        if is_pseudonymous:
            try:
                review.get_anonymous_name()
            except Exception:
                # Continue even if anonymous name creation fails
                pass

        try:
            return 201, ReviewOut.from_orm(review, user)
        except Exception:
            return 500, {"message": "Review created but error retrieving review data."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/{article_id}/reviews/",
    response={200: PaginatedReviewSchema, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_reviews(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    try:
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return 404, {"message": "Article not found."}
        except Exception:
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            reviews = Review.objects.filter(article=article).order_by("-created_at")
        except Exception:
            return 500, {"message": "Error retrieving reviews. Please try again."}

        if community_id:
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            except Exception:
                return 500, {"message": "Error retrieving community. Please try again."}

            # if the community is hidden, only members can view reviews
            if not community.is_member(request.auth) and community.type == "hidden":
                return 403, {"message": "You are not a member of this community."}

            try:
                reviews = reviews.filter(community=community)
            except Exception:
                return 500, {
                    "message": "Error filtering reviews by community. Please try again."
                }
        else:
            try:
                reviews = reviews.filter(community=None)
            except Exception:
                return 500, {"message": "Error filtering reviews. Please try again."}

        try:
            paginator = Paginator(reviews, size)
            page_obj = paginator.page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        current_user: Optional[User] = None if not request.auth else request.auth

        try:
            items = [
                ReviewOut.from_orm(review, current_user)
                for review in page_obj.object_list
            ]

            return 200, PaginatedReviewSchema(
                items=items, total=paginator.count, page=page, size=size
            )
        except Exception:
            return 500, {"message": "Error formatting review data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/reviews/{review_id}/",
    response={200: ReviewOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_review(request, review_id: int):
    try:
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        user = request.auth

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, ReviewOut.from_orm(review, user)
        except Exception:
            return 500, {"message": "Error formatting review data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "/reviews/{review_id}/",
    response={201: ReviewOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_review(request, review_id: int, review_data: ReviewUpdateSchema):
    try:
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        user = request.auth

        # Check if the review belongs to the user
        if review.user != user:
            return 403, {"message": "You do not have permission to update this review."}

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            # Update the review with new data if provided
            review.rating = review_data.rating or review.rating
            review.subject = review_data.subject or review.subject
            review.content = review_data.content or review.content

            review.save()
        except Exception:
            return 500, {"message": "Error updating review. Please try again."}

        try:
            return 201, ReviewOut.from_orm(review, user)
        except Exception:
            return 500, {"message": "Review updated but error retrieving review data."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "/reviews/{review_id}/",
    response={201: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    try:
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        user = request.auth  # Assuming user is authenticated

        if review.user != user:
            return 403, {"message": "You do not have permission to delete this review."}

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            review.subject = "[deleted]"
            review.content = "[deleted]"
            review.deleted_at = timezone.now()
            review.save()
        except Exception:
            return 500, {"message": "Error deleting review. Please try again."}

        return 201, {"message": "Review deleted successfully."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


"""
Endpoints for comments on reviews
"""


# Create a Comment
@router.post(
    "reviews/{review_id}/comments/",
    response={201: ReviewCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def create_comment(request, review_id: int, payload: ReviewCommentCreateSchema):
    try:
        user = request.auth
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        if review.user == user and payload.rating > 0:
            return 400, {"message": "You can't rate your own review."}

        parent_comment = None

        if payload.parent_id:
            try:
                parent_comment = ReviewComment.objects.get(id=payload.parent_id)
            except ReviewComment.DoesNotExist:
                return 404, {"message": "Parent comment not found."}
            except Exception:
                return 500, {
                    "message": "Error retrieving parent comment. Please try again."
                }

            if parent_comment.is_deleted:
                return 400, {"message": "You can't reply to a deleted comment."}

            nesting_level = 1
            current_parent = parent_comment

            while current_parent.parent:
                nesting_level += 1
                current_parent = current_parent.parent
                if nesting_level >= MAX_NESTING_LEVEL:
                    return 400, {
                        "message": f"Exceeded maximum comment nesting level of {MAX_NESTING_LEVEL}"
                    }

        # if payload.rating == 0:
        #     previous_comment = ReviewComment.objects.filter(review=review, author=user, rating__isnull=False).first()
        #     rating_to_store = None if previous_comment else 0
        # else:
        if payload.rating > 0:
            try:
                ratingCommunity = review.community
                ReviewCommentRating.objects.update_or_create(
                    review=review,
                    user=user,
                    community=ratingCommunity,
                    defaults={"rating": payload.rating},
                )
            except Exception:
                return 500, {"message": "Error updating rating. Please try again."}

        is_pseudonymous = False
        try:
            if review.community_article and review.community_article.is_pseudonymous:
                is_pseudonymous = True
        except Exception:
            return 500, {
                "message": "Error checking article pseudonymity. Please try again."
            }

        try:
            comment = ReviewComment.objects.create(
                review=review,
                community=review.community,
                author=user,
                rating=payload.rating,
                content=payload.content,
                parent=parent_comment,
                is_pseudonymous=is_pseudonymous,
            )
        except Exception:
            return 500, {"message": "Error creating comment. Please try again."}

        if is_pseudonymous:
            try:
                # Create an anonymous name for the user who created the comment
                comment.get_anonymous_name()
            except Exception:
                # Continue even if anonymous name creation fails
                pass

        # Return comment with replies
        try:
            return 201, ReviewCommentOut.from_orm_with_replies(comment, user)
        except Exception:
            return 500, {
                "message": "Comment created but error retrieving comment data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get a Comment
@router.get(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    try:
        try:
            comment = ReviewComment.objects.get(id=comment_id)
        except ReviewComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            comment.community
            and not comment.community.is_member(current_user)
            and comment.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, ReviewCommentOut.from_orm_with_replies(comment, current_user)
        except Exception:
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "reviews/{review_id}/comments/",
    response={200: List[ReviewCommentOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_review_comments(request, review_id: int):
    try:
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            review.community
            and not review.community.is_member(current_user)
            and review.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        try:
            comments = (
                ReviewComment.objects.filter(review=review, parent=None)
                .filter(Q(is_deleted=False) | Q(review_replies__isnull=False))
                .select_related("author")
                .order_by("-created_at")
            )
        except Exception:
            return 500, {"message": "Error retrieving comments. Please try again."}

        try:
            result = [
                ReviewCommentOut.from_orm_with_replies(comment, current_user)
                for comment in comments
            ]
            return 200, result
        except Exception:
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.put(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: ReviewCommentUpdateSchema):
    try:
        try:
            comment = ReviewComment.objects.get(id=comment_id)
        except ReviewComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        if comment.author != request.auth:
            return 403, {
                "message": "You do not have permission to update this comment."
            }

        if comment.community and not comment.community.is_member(request.auth):
            return 403, {"message": "You are not a member of this community."}

        if comment.is_deleted:
            return 403, {"message": "You can't update a deleted comment."}

        review = comment.review
        user = request.auth

        if payload.rating > 0:
            try:
                ratingCommunity = review.community
                ReviewCommentRating.objects.update_or_create(
                    review=review,
                    user=user,
                    community=ratingCommunity,
                    defaults={"rating": payload.rating},
                )
            except Exception:
                return 500, {"message": "Error updating rating. Please try again."}

        try:
            comment.content = payload.content or comment.content
            comment.rating = payload.rating or comment.rating
            comment.save()
        except Exception:
            return 500, {"message": "Error updating comment. Please try again."}

        try:
            return 200, ReviewCommentOut.from_orm_with_replies(comment, request.auth)
        except Exception:
            return 500, {
                "message": "Comment updated but error retrieving comment data."
            }
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.delete(
    "reviews/comments/{comment_id}/",
    response={204: None, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def delete_comment(request, comment_id: int):
    try:
        user = request.auth
        try:
            comment = ReviewComment.objects.get(id=comment_id)
        except ReviewComment.DoesNotExist:
            return 404, {"message": "Comment not found."}
        except Exception:
            return 500, {"message": "Error retrieving comment. Please try again."}

        # Check if the user is the owner of the comment or has permission to delete it
        if comment.author != user:
            return 403, {
                "message": "You do not have permission to delete this comment."
            }

        try:
            # Delete reactions associated with the comment
            Reaction.objects.filter(
                content_type__model="reviewcomment", object_id=comment.id
            ).delete()

            comment_rating = ReviewCommentRating.objects.filter(
                review=comment.review, user=user, community=comment.community
            ).first()
            if comment_rating and comment_rating.rating == comment.rating:
                last_comment = (
                    ReviewComment.objects.filter(
                        review=comment.review, author=comment.author, is_deleted=False
                    )
                    .exclude(id=comment.id)
                    .exclude(rating=0)
                    .order_by("-created_at")
                    .only("id", "rating")
                    .first()
                )
                if last_comment and last_comment.rating > 0:
                    comment_rating.rating = last_comment.rating
                    comment_rating.save()
                else:
                    comment_rating.delete()

            # Logically delete the comment by clearing its content and marking it as deleted
            comment.content = "[deleted]"
            comment.is_deleted = True
            comment.rating = None
            comment.save()
        except Exception:
            return 500, {"message": "Error deleting comment. Please try again."}

        return 204, None
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}


# Get Rating for a review by user
@router.get(
    "reviews/{review_id}/rating/",
    response={
        200: ReviewCommentRatingByUserOut,
        codes_4xx: Message,
        codes_5xx: Message,
    },
    auth=JWTAuth(),
)
def get_rating(request, review_id: int):
    try:
        user = request.auth
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception:
            return 500, {"message": "Error retrieving review. Please try again."}

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            comment = (
                ReviewComment.objects.filter(
                    review=review, author=user, is_deleted=False
                )
                .exclude(rating=0)
                .order_by("-created_at")
                .only("id", "rating")
                .first()
            )

            if not comment:
                return 200, {"rating": 0}

            return 200, {"rating": comment.rating}
        except Exception:
            return 500, {"message": "Error retrieving rating. Please try again."}
    except Exception:
        return 500, {"message": "An unexpected error occurred. Please try again later."}
