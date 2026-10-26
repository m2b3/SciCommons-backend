from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article


class ArticleSlugTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="slug-author", email="slug-author@example.com", password="test-password"
        )

    def create_article(self, title):
        return Article.objects.create(
            title=title, abstract="Test abstract", submission_type="Public", submitter=self.user
        )

    def test_long_title_generates_bounded_slug(self):
        article = self.create_article("a" * 500)
        article.refresh_from_db()
        self.assertEqual(article.title, "a" * 500)
        self.assertEqual(article.slug, "a" * 255)

    def test_duplicate_maximum_length_slug_leaves_room_for_suffix(self):
        first = self.create_article("a" * 255)
        second = self.create_article("a" * 255)
        second.refresh_from_db()
        self.assertNotEqual(first.slug, second.slug)
        self.assertLessEqual(len(second.slug), 255)
        self.assertRegex(second.slug, r"^a+-[0-9a-f]{8}$")

    def test_non_ascii_title_generates_nonempty_unique_slugs(self):
        first = self.create_article("科学研究")
        second = self.create_article("科学研究")
        self.assertTrue(first.slug)
        self.assertTrue(second.slug)
        self.assertNotEqual(first.slug, second.slug)

    def test_saved_slug_is_preserved_when_title_changes(self):
        article = self.create_article("Original title")
        original_slug = article.slug
        article.title = "a" * 500
        article.save()
        article.refresh_from_db()
        self.assertEqual(article.slug, original_slug)
