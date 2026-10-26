from django.test import TestCase

from articles.models import Article, Review
from articles.schemas import serialize_review_versions
from users.models import User


class ReviewRatingHistoryTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="reviewer", email="reviewer@example.com", password=None)
        article = Article.objects.create(
            title="Review history", abstract="Test abstract", submission_type="Public", submitter=user
        )
        self.review = Review.objects.create(
            article=article, user=user, rating=5, subject="Original", content="Review text"
        )

    def test_rating_only_edit_preserves_previous_rating(self):
        self.review.rating = 3
        self.review.save()
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 3)
        self.assertEqual(self.review.version, 2)
        versions = serialize_review_versions(self.review)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].rating, 5)
        self.assertEqual(versions[0].subject, "Original")
        self.assertEqual(versions[0].content, "Review text")
        self.assertEqual(versions[0].version, 1)

    def test_rating_and_text_edit_creates_only_one_version(self):
        self.review.rating = 3
        self.review.content = "Updated review text"
        self.review.save()
        self.review.refresh_from_db()
        self.assertEqual(self.review.version, 2)
        version = self.review.versions.get()
        self.assertEqual(version.rating, 5)
        self.assertEqual(version.content, "Review text")

    def test_unchanged_review_does_not_create_version(self):
        self.review.save()
        self.review.refresh_from_db()
        self.assertEqual(self.review.version, 1)
        self.assertFalse(self.review.versions.exists())
