from typing import List, Optional

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from ninja import Router
from ninja.responses import codes_4xx

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
    response={201: ReviewOut, codes_4xx: Message, 500: Message},
    auth=JWTAuth(),
)
def create_review(
    request,
    article_id: int,
    review_data: CreateReviewSchema,
    community_id: Optional[int] = None,
):
    article = Article.objects.get(id=article_id)
    user = request.auth

    if article.submitter == user:
        return 400, {"message": "You can't review your own article."}

    existing_review = Review.objects.filter(article=article, user=user)

    if community_id:
        community = Community.objects.get(id=community_id)
        if not community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        community_article = CommunityArticle.objects.get(
            article=article, community=community
        )

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

        if existing_review.filter(community=community).exists():
            return 400, {
                "message": "You have already reviewed this article in this community."
            }

    else:
        if existing_review.filter(community__isnull=True).exists():
            return 400, {"message": "You have already reviewed this article."}

        review_type = Review.PUBLIC

    review = Review.objects.create(
        article=article,
        user=user,
        community=community if community_id else None,
        community_article=community_article if community_id else None,
        review_type=review_type,
        rating=review_data.rating,
        subject=review_data.subject,
        content=review_data.content,
    )

    review.get_anonymous_name()

    return 201, ReviewOut.from_orm(review, user)


@router.get(
    "/{article_id}/reviews/",
    response={200: PaginatedReviewSchema, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def list_reviews(
    request, article_id: int, community_id: int = None, page: int = 1, size: int = 10
):
    article = Article.objects.get(id=article_id)
    reviews = Review.objects.filter(article=article).order_by("-created_at")

    if community_id:
        community = Community.objects.get(id=community_id)
        # if the community is hidden, only members can view reviews
        if not community.is_member(request.auth) and community.type == "hidden":
            return 403, {"message": "You are not a member of this community."}

        reviews = reviews.filter(community=community)
    else:
        reviews = reviews.filter(community=None)

    paginator = Paginator(reviews, size)
    page_obj = paginator.page(page)
    current_user: Optional[User] = None if not request.auth else request.auth

    items = [
        ReviewOut.from_orm(review, current_user) for review in page_obj.object_list
    ]

    return PaginatedReviewSchema(
        items=items, total=paginator.count, page=page, size=size
    )


@router.get(
    "/reviews/{review_id}/",
    response={200: ReviewOut, 404: Message, 500: Message},
    auth=OptionalJWTAuth,
)
def get_review(request, review_id: int):
    review = Review.objects.get(id=review_id)
    user = request.auth

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    return 200, ReviewOut.from_orm(review, user)


@router.put(
    "/reviews/{review_id}/",
    response={201: ReviewOut, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def update_review(request, review_id: int, review_data: ReviewUpdateSchema):
    review = Review.objects.get(id=review_id)
    user = request.auth

    # Check if the review belongs to the user
    if review.user != user:
        return 403, {"message": "You do not have permission to update this review."}

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    # Update the review with new data if provided
    review.rating = review_data.rating or review.rating
    review.subject = review_data.subject or review.subject
    review.content = review_data.content or review.content

    review.save()

    return 201, ReviewOut.from_orm(review, user)


@router.delete(
    "/reviews/{review_id}/",
    response={201: Message, 404: Message, 500: Message},
    auth=JWTAuth(),
)
def delete_review(request, review_id: int):
    review = Review.objects.get(id=review_id)
    user = request.auth  # Assuming user is authenticated

    if review.user != user:
        return 403, {"message": "You do not have permission to delete this review."}

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    review.subject = "[deleted]"
    review.content = "[deleted]"
    review.deleted_at = timezone.now()

    return 201, {"message": "Review deleted successfully."}


"""
Endpoints for comments on reviews
"""


# Create a Comment
@router.post(
    "reviews/{review_id}/comments/", response={201: ReviewCommentOut}, auth=JWTAuth()
)
def create_comment(request, review_id: int, payload: ReviewCommentCreateSchema):
    user = request.auth
    review = Review.objects.get(id=review_id)

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}
    
    if review.user == user and payload.rating > 0:
        return 400, {"message": "You can't rate your own review."}

    parent_comment = None

    if payload.parent_id:
        parent_comment = ReviewComment.objects.get(id=payload.parent_id)
        if parent_comment.is_deleted:
            return 400, {"message": "You can't reply to a deleted comment."}

        nesting_level = 1
        current_parent = parent_comment

        while current_parent.parent:
            nesting_level += 1
            current_parent = current_parent.parent
            if nesting_level >= MAX_NESTING_LEVEL:
                return 400, {"message": f"Exceeded maximum comment nesting level of {MAX_NESTING_LEVEL}"}
            
    # if payload.rating == 0:
    #     previous_comment = ReviewComment.objects.filter(review=review, author=user, rating__isnull=False).first()
    #     rating_to_store = None if previous_comment else 0
    # else:
    if payload.rating > 0:
        ratingCommunity = review.community
        ReviewCommentRating.objects.update_or_create(
            review=review, user=user, community=ratingCommunity, defaults={"rating": payload.rating}
        )

    comment = ReviewComment.objects.create(
        review=review,
        community=review.community,
        author=user,
        rating=payload.rating,
        content=payload.content,
        parent=parent_comment,
    )
    # Create an anonymous name for the user who created the comment
    comment.get_anonymous_name()

    # Return comment with replies
    return 201, ReviewCommentOut.from_orm_with_replies(comment, user)


# Get a Comment
@router.get(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, 404: Message},
    auth=OptionalJWTAuth,
)
def get_comment(request, comment_id: int):
    comment = ReviewComment.objects.get(id=comment_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        comment.community
        and not comment.community.is_member(current_user)
        and comment.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    return 200, ReviewCommentOut.from_orm_with_replies(comment, current_user)


@router.get(
    "reviews/{review_id}/comments/",
    response=List[ReviewCommentOut],
    auth=OptionalJWTAuth,
)
def list_review_comments(request, review_id: int):
    review = Review.objects.get(id=review_id)
    current_user: Optional[User] = None if not request.auth else request.auth

    if (
        review.community
        and not review.community.is_member(current_user)
        and review.community.type == "hidden"
    ):
        return 403, {"message": "You are not a member of this community."}

    comments = (
        ReviewComment.objects.filter(review=review, parent=None)
        .filter(Q(is_deleted=False) | Q(review_replies__isnull=False))
        .select_related("author")
        .order_by("-created_at")
    )

    return [
        ReviewCommentOut.from_orm_with_replies(comment, current_user)
        for comment in comments
    ]


@router.put(
    "reviews/comments/{comment_id}/",
    response={200: ReviewCommentOut, 403: Message},
    auth=JWTAuth(),
)
def update_comment(request, comment_id: int, payload: ReviewCommentUpdateSchema):
    comment = ReviewComment.objects.get(id=comment_id)

    if comment.author != request.auth:
        return 403, {"message": "You do not have permission to update this comment."}

    if comment.community and not comment.community.is_member(request.auth):
        return 403, {"message": "You are not a member of this community."}
    
    if comment.is_deleted:
        return 403, {"message": "You can't update a deleted comment."}
    
    review = comment.review
    user = request.auth

    if payload.rating > 0:
        ratingCommunity = review.community
        ReviewCommentRating.objects.update_or_create(
            review=review, user=user, community=ratingCommunity, defaults={"rating": payload.rating}
        )

    comment.content = payload.content or comment.content
    comment.rating = payload.rating or comment.rating

    comment.save()

    return 200, ReviewCommentOut.from_orm_with_replies(comment, request.auth)


@router.delete(
    "reviews/comments/{comment_id}/", response={204: None, 403: Message}, auth=JWTAuth()
)
def delete_comment(request, comment_id: int):
    user = request.auth
    comment = ReviewComment.objects.get(id=comment_id)

    # Check if the user is the owner of the comment or has permission to delete it
    if comment.author != user:
        return 403, {"message": "You do not have permission to delete this comment."}

    # Delete reactions associated with the comment
    Reaction.objects.filter(
        content_type__model="reviewcomment", object_id=comment.id
    ).delete()

    comment_rating = ReviewCommentRating.objects.filter(review=comment.review, user=user, community=comment.community).first()
    if comment_rating and comment_rating.rating == comment.rating:
        last_comment = ReviewComment.objects.filter(
                review=comment.review, 
                author=comment.author,
                is_deleted=False
            ).exclude(
                id=comment.id
            ).exclude(
                rating=0
            ).order_by('-created_at').only('id', 'rating').first()
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

    return 204, None

# Get Rating for a review by user
@router.get(
    "reviews/{review_id}/rating/", response={200: ReviewCommentRatingByUserOut, 404: Message}, auth=JWTAuth()
)
def get_rating(request, review_id: int):
    user = request.auth
    review = Review.objects.get(id=review_id)

    if review.community and not review.community.is_member(user):
        return 403, {"message": "You are not a member of this community."}

    comment = ReviewComment.objects.filter(
                    review=review, 
                    author=user,
                    is_deleted=False
                ).exclude(
                    rating=0
                ).order_by('-created_at').only('id', 'rating').first()
    if not comment:
        return 200, {'rating': 0}

    return 200, {'rating': comment.rating}