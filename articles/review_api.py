import logging
from typing import List, Optional

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, Q
from django.utils import timezone
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import (
    AnonymousIdentity,
    Article,
    Reaction,
    Review,
    ReviewComment,
    ReviewCommentRating,
    ReviewVersion,
)
from articles.schemas import (
    CommunityArticleOut,
    CreateReviewSchema,
    Message,
    PaginatedReviewSchema,
    ReviewCommentCreateSchema,
    ReviewCommentOut,
    ReviewCommentRatingByUserOut,
    ReviewCommentUpdateSchema,
    ReviewOut,
    ReviewUpdateSchema,
    ReviewVersionSchema,
)
from communities.models import Community, CommunityArticle
from myapp.feature_flags import MAX_NESTING_LEVEL
from myapp.schemas import UserStats
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import User

router = Router(tags=["Reviews"])

# Module-level logger
logger = logging.getLogger(__name__)


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
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        user = request.auth

        # Uncomment this after testing
        # if article.submitter == user:
        #     return 400, {"message": "You can't review your own article."}

        try:
            existing_review = Review.objects.filter(article=article, user=user)
        except Exception as e:
            logger.error(f"Error checking existing reviews: {e}")
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
            except Exception as e:
                logger.error(f"Error retrieving community: {e}")
                return 500, {"message": "Error retrieving community. Please try again."}

            if not community.is_member(user):
                return 403, {"message": "You are not a member of this community."}

            try:
                community_article = CommunityArticle.objects.get(
                    article=article, community=community
                )
            except CommunityArticle.DoesNotExist:
                return 404, {"message": "Article not found in this community."}
            except Exception as e:
                logger.error(f"Error retrieving community article: {e}")
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
            except Exception as e:
                logger.error(f"Error checking existing reviews: {e}")
                return 500, {
                    "message": "Error checking existing reviews. Please try again."
                }

        else:
            try:
                if existing_review.filter(community__isnull=True).exists():
                    return 400, {"message": "You have already reviewed this article."}
            except Exception as e:
                logger.error(f"Error checking existing reviews: {e}")
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
        except Exception as e:
            logger.error(f"Error creating review: {e}")
            return 500, {"message": "Error creating review. Please try again."}

        if is_pseudonymous:
            try:
                review.get_anonymous_name()
            except Exception as e:
                logger.error(f"Error creating anonymous name for review: {e}")
                # Continue even if anonymous name creation fails
                pass

        try:
            return 201, ReviewOut.from_orm(review, user)
        except Exception as e:
            logger.error(f"Error formatting review data: {e}")
            return 500, {"message": "Review created but error retrieving review data."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return 500, {"message": "Error retrieving article. Please try again."}

        try:
            # reviews = Review.objects.filter(article=article).order_by("-created_at")
            reviews = (
                Review.objects.filter(article=article)
                .select_related("user", "community", "community_article", "article")
                .prefetch_related(
                    Prefetch(
                        "versions",
                        queryset=ReviewVersion.objects.order_by("-version"),
                        to_attr="prefetched_versions",
                    )
                )
                .order_by("-created_at")
            )
        except Exception as e:
            logger.error(f"Error retrieving reviews: {e}")
            return 500, {"message": "Error retrieving reviews. Please try again."}

        if community_id:
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                return 404, {"message": "Community not found."}
            except Exception as e:
                logger.error(f"Error retrieving community: {e}")
                return 500, {"message": "Error retrieving community. Please try again."}

            # if the community is hidden, only members can view reviews
            if not community.is_member(request.auth) and community.type == "hidden":
                return 403, {"message": "You are not a member of this community."}

            reviews = reviews.filter(community=community)
        else:
            reviews = reviews.filter(community=None)

        try:
            paginator = Paginator(reviews, size)
            page_obj = paginator.page(page)
        except Exception:
            return 400, {
                "message": "Invalid pagination parameters. Please check page number and size."
            }

        current_user: Optional[User] = None if not request.auth else request.auth

        try:
            # items = [
            #     ReviewOut.from_orm(review, current_user)
            #     for review in page_obj.object_list
            # ]
            reviews_list = list(page_obj.object_list)

            # Bulk fetch related data to avoid N+1 queries
            review_ids = [r.id for r in reviews_list]
            review_user_ids = {r.user_id for r in reviews_list}
            review_community_ids = {
                r.community_id for r in reviews_list if r.community_id
            }

            comments_count_map = dict(
                ReviewComment.objects.filter(review_id__in=review_ids, is_deleted=False)
                .values("review_id")
                .annotate(count=Count("id"))
                .values_list("review_id", "count")
            )

            comments_ratings_map = dict(
                ReviewCommentRating.objects.filter(
                    review_id__in=review_ids,
                    community_id__in=(
                        review_community_ids if review_community_ids else [None]
                    ),
                )
                .exclude(user_id__in=review_user_ids)
                .values("review_id")
                .annotate(avg_rating=Avg("rating"))
                .values_list("review_id", "avg_rating")
            )

            # Fetch and map anonymous identities in bulk
            pseudonyms = {
                (anon.article_id, anon.user_id, anon.community_id): anon
                for anon in AnonymousIdentity.objects.filter(
                    article_id=article.id, user_id__in=review_user_ids
                )
            }

            # Bulk fetch CommunityArticles if needed
            ca_map = {
                (ca.article_id, ca.community_id): ca
                for ca in CommunityArticle.objects.filter(
                    article_id=article.id, community_id__in=review_community_ids
                )
            }

            # Build the response
            items = []
            for review in reviews_list:
                user = UserStats.from_model(
                    review.user, basic_details_with_reputation=True
                )

                if review.is_pseudonymous:
                    pseudonym = pseudonyms.get(
                        (article.id, review.user_id, review.community_id)
                    )
                    if pseudonym:
                        user.username = pseudonym.fake_name
                        user.profile_pic_url = pseudonym.identicon

                community_article = None
                ca = ca_map.get((article.id, review.community_id))
                if ca:
                    community_article = CommunityArticleOut.from_orm(ca, current_user)

                versions = [
                    ReviewVersionSchema.from_orm(version)
                    for version in getattr(review, "prefetched_versions", [])[:3]
                ]

                comments_rating = round(comments_ratings_map.get(review.id, 0) or 0, 1)

                items.append(
                    ReviewOut(
                        id=review.id,
                        user=user,
                        article_id=review.article.id,
                        rating=review.rating,
                        review_type=review.review_type,
                        subject=review.subject,
                        content=review.content,
                        version=review.version,
                        created_at=review.created_at,
                        updated_at=review.updated_at,
                        deleted_at=review.deleted_at,
                        comments_count=comments_count_map.get(review.id, 0),
                        is_author=review.user_id
                        == (current_user.id if current_user else None),
                        is_approved=review.is_approved,
                        versions=versions,
                        is_pseudonymous=review.is_pseudonymous,
                        community_article=community_article,
                        comments_ratings=comments_rating,
                    )
                )

            has_user_reviewed = (
                Review.objects.filter(article=article, user=current_user).exists()
                if current_user and not isinstance(current_user, bool)
                else False
            )

            return 200, PaginatedReviewSchema(
                items=items,
                total=paginator.count,
                page=page,
                size=size,
                has_user_reviewed=has_user_reviewed,
            )
        except Exception as e:
            logger.error(f"Error formatting review data: {e}")
            return 500, {"message": "Error formatting review data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
            return 500, {"message": "Error retrieving review. Please try again."}

        user = request.auth

        if review.community and not review.community.is_member(user):
            return 403, {"message": "You are not a member of this community."}

        try:
            return 200, ReviewOut.from_orm(review, user)
        except Exception as e:
            logger.error(f"Error formatting review data: {e}")
            return 500, {"message": "Error formatting review data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
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
        except Exception as e:
            logger.error(f"Error updating review: {e}")
            return 500, {"message": "Error updating review. Please try again."}

        try:
            return 201, ReviewOut.from_orm(review, user)
        except Exception as e:
            logger.error(f"Error formatting review data: {e}")
            return 500, {"message": "Review updated but error retrieving review data."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
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
        except Exception as e:
            logger.error(f"Error deleting review: {e}")
            return 500, {"message": "Error deleting review. Please try again."}

        return 201, {"message": "Review deleted successfully."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
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
            except Exception as e:
                logger.error(f"Error retrieving parent comment: {e}")
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
            except Exception as e:
                logger.error(f"Error updating rating: {e}")
                return 500, {"message": "Error updating rating. Please try again."}

        is_pseudonymous = False
        try:
            if review.community_article and review.community_article.is_pseudonymous:
                is_pseudonymous = True
        except Exception as e:
            logger.error(f"Error checking article pseudonymity: {e}")
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
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            return 500, {"message": "Error creating comment. Please try again."}

        if is_pseudonymous:
            try:
                # Create an anonymous name for the user who created the comment
                comment.get_anonymous_name()
            except Exception as e:
                logger.error(f"Error creating anonymous name for comment: {e}")
                # Continue even if anonymous name creation fails
                pass

        # Return comment with replies
        try:
            return 201, ReviewCommentOut.from_orm_with_replies(comment, user)
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {
                "message": "Comment created but error retrieving comment data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
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
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "reviews/{review_id}/comments/",
    response={200: List[ReviewCommentOut], codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def list_review_comments(request, review_id: int):
    try:
        try:
            # review = Review.objects.get(id=review_id)
            review = Review.objects.select_related("article", "community").get(
                id=review_id
            )
        except Review.DoesNotExist:
            return 404, {"message": "Review not found."}
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
            return 500, {"message": "Error retrieving review. Please try again."}

        current_user: Optional[User] = None if not request.auth else request.auth

        if (
            review.community
            and not review.community.is_member(current_user)
            and review.community.type == "hidden"
        ):
            return 403, {"message": "You are not a member of this community."}

        # try:
        #     comments = (
        #         ReviewComment.objects.filter(review=review, parent=None)
        #         .filter(Q(is_deleted=False) | Q(review_replies__isnull=False))
        #         .select_related("author")
        #         .order_by("-created_at")
        #     )
        # except Exception:
        #     return 500, {"message": "Error retrieving comments. Please try again."}

        try:
            # Root comments (parent=None) with replies
            root_comments = list(
                ReviewComment.objects.filter(review=review, parent=None)
                .filter(Q(is_deleted=False) | Q(review_replies__isnull=False))
                .select_related("author")
                .prefetch_related(
                    "review_replies__author", "reactions", "review_replies__reactions"
                )
                .order_by("-created_at")
            )

            # Collect all comments and replies
            all_comments = root_comments + [
                reply for rc in root_comments for reply in rc.review_replies.all()
            ]
            all_comment_ids = [c.id for c in all_comments]

            upvote_map = dict(
                Reaction.objects.filter(
                    content_type__model="reviewcomment",
                    object_id__in=all_comment_ids,
                    vote=1,
                )
                .values("object_id")
                .annotate(count=Count("id"))
                .values_list("object_id", "count")
            )

            # Bulk fetch pseudonyms if needed
            pseudonym_map = {}
            pseudonymous_authors = [
                (
                    c.author_id,
                    c.review.article_id,
                    c.community_id or review.community_id,
                )
                for c in all_comments
                if c.is_pseudonymous
            ]
            if pseudonymous_authors:
                pseudonyms = AnonymousIdentity.objects.filter(
                    article=review.article,
                    community=review.community,
                    user_id__in={uid for uid, _, _ in pseudonymous_authors},
                )
                pseudonym_map = {
                    (p.user_id, p.article_id, p.community_id): p for p in pseudonyms
                }

            def serialize_comment(comment: ReviewComment) -> ReviewCommentOut:
                user = UserStats.from_model(comment.author, basic_details=True)
                if comment.is_pseudonymous:
                    key = (comment.author_id, review.article_id, review.community_id)
                    pseudonym = pseudonym_map.get(key)
                    if pseudonym:
                        user.username = pseudonym.fake_name
                        user.profile_pic_url = pseudonym.identicon

                return ReviewCommentOut(
                    id=comment.id,
                    rating=(
                        comment.rating if review.user_id != comment.author_id else None
                    ),
                    author=user,
                    content=comment.content,
                    created_at=comment.created_at,
                    upvotes=upvote_map.get(comment.id, 0),
                    replies=[],  # to be filled later
                    is_author=(
                        (comment.author_id == current_user.id)
                        if current_user
                        else False
                    ),
                    is_deleted=comment.is_deleted,
                    is_pseudonymous=comment.is_pseudonymous,
                )

            # Serialize all comments
            comment_map = {c.id: serialize_comment(c) for c in all_comments}

            # Assign replies
            for root in root_comments:
                root_out = comment_map[root.id]
                root_out.replies = [
                    comment_map[reply.id] for reply in root.review_replies.all()
                ]

            return 200, [comment_map[rc.id] for rc in root_comments]
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {"message": "Error formatting comment data. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
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
            except Exception as e:
                logger.error(f"Error updating rating: {e}")
                return 500, {"message": "Error updating rating. Please try again."}

        try:
            comment.content = payload.content or comment.content
            comment.rating = payload.rating or comment.rating
            comment.save()
        except Exception as e:
            logger.error(f"Error updating comment: {e}")
            return 500, {"message": "Error updating comment. Please try again."}

        try:
            return 200, ReviewCommentOut.from_orm_with_replies(comment, request.auth)
        except Exception as e:
            logger.error(f"Error formatting comment data: {e}")
            return 500, {
                "message": "Comment updated but error retrieving comment data."
            }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving comment: {e}")
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
        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            return 500, {"message": "Error deleting comment. Please try again."}

        return 204, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving review: {e}")
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
        except Exception as e:
            logger.error(f"Error retrieving rating: {e}")
            return 500, {"message": "Error retrieving rating. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
