from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from articles import discussion_api, review_api
from articles.models import (
    Article,
    Discussion,
    DiscussionComment,
    Review,
    ReviewComment,
    ReviewVersion,
)
from articles.schemas import ReviewOut

User = get_user_model()


class DeleteWindowApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", email="author@example.com", password="password123"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Delete Window Article",
            abstract="Test abstract",
            authors=["Author One"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.review = Review.objects.create(
            article=self.article,
            user=self.user,
            rating=5,
            subject="Review subject",
            content="Review content",
        )
        self.discussion = Discussion.objects.create(
            article=self.article,
            author=self.user,
            topic="Discussion topic",
            content="Discussion content",
        )

    def request_for(self, user):
        return SimpleNamespace(auth=user)

    def test_review_delete_within_window_clears_content(self):
        status, _ = review_api.delete_review(self.request_for(self.user), self.review.id)

        self.assertEqual(status, 201)
        self.review.refresh_from_db()
        self.assertEqual(self.review.subject, "")
        self.assertEqual(self.review.content, "")
        self.assertIsNotNone(self.review.deleted_at)

    def test_review_delete_takes_the_version_history_with_it(self):
        """
        Review.save() snapshots the previous subject/content into ReviewVersion whenever they
        change, so blanking the fields during a delete archives the very text being removed -
        on top of whatever earlier edits already left behind. Both have to go.
        """
        self.review.subject = "Edited subject"
        self.review.content = "Edited content"
        self.review.save()
        self.assertTrue(ReviewVersion.objects.filter(review=self.review).exists())

        status, _ = review_api.delete_review(self.request_for(self.user), self.review.id)

        self.assertEqual(status, 201)
        self.assertFalse(ReviewVersion.objects.filter(review=self.review).exists())

    def test_from_orm_withholds_versions_for_a_deleted_review(self):
        self.review.deleted_at = timezone.now()
        self.review.save(update_fields=["deleted_at"])
        # Force history back in so this covers the serializer guard, not just the purge above.
        ReviewVersion.objects.create(
            review=self.review,
            rating=5,
            subject="Secret subject",
            content="Secret content",
            version=1,
        )

        payload = ReviewOut.from_orm(self.review, self.user)

        self.assertEqual(payload.versions, [])

    def test_list_reviews_withholds_versions_for_a_deleted_review(self):
        """
        list_reviews builds ReviewOut inline off a prefetch instead of calling from_orm, so it
        needs its own coverage - the leak lived in this path and the article page uses it.
        """
        self.review.deleted_at = timezone.now()
        self.review.save(update_fields=["deleted_at"])
        ReviewVersion.objects.create(
            review=self.review,
            rating=5,
            subject="Secret subject",
            content="Secret content",
            version=1,
        )

        status, payload = review_api.list_reviews(self.request_for(self.user), self.article.id)

        self.assertEqual(status, 200)
        listed = [item for item in payload.items if item.id == self.review.id]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].versions, [])

    def test_review_delete_after_window_is_rejected(self):
        Review.objects.filter(id=self.review.id).update(created_at=timezone.now() - timedelta(minutes=6))

        status, payload = review_api.delete_review(self.request_for(self.user), self.review.id)

        self.assertEqual(status, 403)
        self.assertIn("5 minutes", payload["message"])
        self.review.refresh_from_db()
        self.assertIsNone(self.review.deleted_at)
        self.assertEqual(self.review.content, "Review content")

    def test_deleted_review_cannot_be_updated(self):
        self.review.deleted_at = timezone.now()
        self.review.save(update_fields=["deleted_at"])

        status, payload = review_api.update_review(
            self.request_for(self.user),
            self.review.id,
            SimpleNamespace(rating=4, subject="Updated", content="Updated content"),
        )

        self.assertEqual(status, 403)
        self.assertIn("deleted review", payload["message"])
        self.review.refresh_from_db()
        self.assertEqual(self.review.content, "Review content")

    def test_review_comment_delete_preserves_child_reply(self):
        parent = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            content="Parent comment",
        )
        child = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            content="Child reply",
            parent=parent,
        )

        status, _ = review_api.delete_comment(self.request_for(self.user), parent.id)

        self.assertEqual(status, 204)
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_deleted)
        self.assertEqual(parent.content, "")
        self.assertEqual(child.parent_id, parent.id)
        self.assertEqual(child.content, "Child reply")

    def test_discussion_comment_delete_after_window_is_rejected(self):
        comment = DiscussionComment.objects.create(
            discussion=self.discussion,
            author=self.user,
            content="Discussion comment",
        )
        DiscussionComment.objects.filter(id=comment.id).update(
            created_at=timezone.now() - timedelta(minutes=6)
        )

        status, payload = discussion_api.delete_comment(self.request_for(self.user), comment.id)

        self.assertEqual(status, 403)
        self.assertIn("5 minutes", payload["message"])
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)
        self.assertEqual(comment.content, "Discussion comment")

    def test_deleted_discussion_comment_cannot_be_updated(self):
        comment = DiscussionComment.objects.create(
            discussion=self.discussion,
            author=self.user,
            content="Discussion comment",
            is_deleted=True,
        )

        status, payload = discussion_api.update_comment(
            self.request_for(self.user),
            comment.id,
            SimpleNamespace(content="Updated discussion comment"),
        )

        self.assertEqual(status, 403)
        self.assertIn("deleted comment", payload["message"])
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Discussion comment")

    def test_non_author_cannot_delete_comment_inside_window(self):
        comment = DiscussionComment.objects.create(
            discussion=self.discussion,
            author=self.user,
            content="Discussion comment",
        )

        status, _ = discussion_api.delete_comment(self.request_for(self.other_user), comment.id)

        self.assertEqual(status, 403)
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)
