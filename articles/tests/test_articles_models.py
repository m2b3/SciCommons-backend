from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError
from django.test import TestCase, override_settings
from django.utils.text import slugify
from faker import Faker
import shutil
import tempfile

from communities.models import Community

from ..models import (
    AnonymousIdentity,
    Article,
    ArticlePDF,
    Discussion,
    DiscussionComment,
    Reaction,
    Review,
    ReviewComment,
    ReviewVersion,
)

User = get_user_model()
fake = Faker()


class ArticleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article_data = {
            "title": fake.sentence(nb_words=6),
            "abstract": fake.paragraph(nb_sentences=3),
            "authors": [fake.name() for _ in range(3)],
            "submission_type": "Public",
            "submitter": self.user,
            "faqs": [
                {"question": fake.sentence(), "answer": fake.paragraph()}
                for _ in range(2)
            ],
        }

    def test_create_article(self):
        article = Article.objects.create(**self.article_data)
        self.assertEqual(article.title, self.article_data["title"])
        self.assertEqual(article.abstract, self.article_data["abstract"])
        self.assertEqual(article.authors, self.article_data["authors"])
        self.assertEqual(article.submission_type, self.article_data["submission_type"])
        self.assertEqual(article.submitter, self.article_data["submitter"])
        self.assertEqual(article.faqs, self.article_data["faqs"])

    def test_slug_generation(self):
        article = Article.objects.create(**self.article_data)
        expected_slug = slugify(article.title)
        self.assertTrue(article.slug.startswith(expected_slug))

    def test_unique_slug_generation(self):
        article1 = Article.objects.create(**self.article_data)
        article2 = Article.objects.create(**self.article_data)
        self.assertNotEqual(article1.slug, article2.slug)
        self.assertTrue(article2.slug.startswith(slugify(article2.title)))

    def test_article_str(self):
        article = Article.objects.create(**self.article_data)
        self.assertEqual(str(article), article.title)

    def test_article_image_url_optional(self):
        article = Article.objects.create(**self.article_data)
        self.assertFalse(article.article_image_url.name)

    def test_article_link_optional(self):
        article = Article.objects.create(**self.article_data)
        self.assertIsNone(article.article_link)

    def test_article_timestamps(self):
        article = Article.objects.create(**self.article_data)
        self.assertIsNotNone(article.created_at)
        self.assertIsNotNone(article.updated_at)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ArticlePDFModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article_data = {
            "title": fake.sentence(nb_words=6),
            "abstract": fake.paragraph(nb_sentences=3),
            "authors": [fake.name() for _ in range(3)],
            "submission_type": "Public",
            "submitter": self.user,
            "faqs": [
                {"question": fake.sentence(), "answer": fake.paragraph()}
                for _ in range(2)
            ],
        }
        self.article = Article.objects.create(**self.article_data)
        self.pdf_file = SimpleUploadedFile(
            "test.pdf", b"file_content", content_type="application/pdf"
        )

    def test_create_article_pdf(self):
        article_pdf = ArticlePDF.objects.create(
            article=self.article, pdf_file_url=self.pdf_file
        )
        self.assertEqual(article_pdf.article, self.article)
        self.assertTrue(article_pdf.pdf_file_url.name.startswith("article_pdfs/"))

    def test_article_pdf_str(self):
        article_pdf = ArticlePDF.objects.create(
            article=self.article, pdf_file_url=self.pdf_file
        )
        expected_str = f"{self.article.title} - PDF {article_pdf.id}"
        self.assertEqual(str(article_pdf), expected_str)

    def test_uploaded_at_auto_now_add(self):
        article_pdf = ArticlePDF.objects.create(
            article=self.article, pdf_file_url=self.pdf_file
        )
        self.assertIsNotNone(article_pdf.uploaded_at)


class AnonymousIdentityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )

    def test_generate_reddit_style_username(self):
        username = AnonymousIdentity.generate_reddit_style_username()
        self.assertIsInstance(username, str)
        self.assertTrue(len(username) > 0)

    def test_get_or_create_fake_name_creates_new_identity(self):
        fake_name = AnonymousIdentity.get_or_create_fake_name(self.user, self.article)
        self.assertIsInstance(fake_name, str)
        self.assertTrue(len(fake_name) > 0)

        identity = AnonymousIdentity.objects.get(user=self.user, article=self.article)
        self.assertEqual(identity.fake_name, fake_name)

    def test_get_or_create_fake_name_retrieves_existing_identity(self):
        AnonymousIdentity.objects.create(
            user=self.user, article=self.article, fake_name="ExistingFakeName"
        )
        fake_name = AnonymousIdentity.get_or_create_fake_name(self.user, self.article)
        self.assertEqual(fake_name, "ExistingFakeName")

    def test_unique_together_constraint(self):
        AnonymousIdentity.objects.create(
            user=self.user, article=self.article, fake_name="UniqueName1"
        )

        with self.assertRaises(IntegrityError):  # Use the appropriate exception
            AnonymousIdentity.objects.create(
                user=self.user, article=self.article, fake_name="UniqueName2"
            )


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.community = Community.objects.create(name="Test Community")
        self.review_data = {
            "article": self.article,
            "user": self.user,
            "community": self.community,
            "rating": 5,
            "subject": "Great Article",
            "content": "This is a great article. I learned a lot.",
        }

    def test_create_review(self):
        review = Review.objects.create(**self.review_data)
        self.assertEqual(review.article, self.article)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.community, self.community)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.subject, "Great Article")
        self.assertEqual(review.content, "This is a great article. I learned a lot.")
        self.assertEqual(review.version, 1)

    def test_update_review_versioning(self):
        review = Review.objects.create(**self.review_data)
        review.content = "This is an updated review."
        review.save()

        # Ensure a new version was created
        review_versions = ReviewVersion.objects.filter(review=review)
        self.assertEqual(review_versions.count(), 1)
        self.assertEqual(
            review_versions.first().content, "This is a great article. I learned a lot."
        )

        # Ensure the version number was incremented
        review.refresh_from_db()
        self.assertEqual(review.version, 2)

    def test_get_anonymous_name(self):
        review = Review.objects.create(**self.review_data)
        anonymous_name = review.get_anonymous_name()
        self.assertIsInstance(anonymous_name, str)
        self.assertTrue(len(anonymous_name) > 0)

    def test_unique_together_constraint(self):
        Review.objects.create(**self.review_data)
        with self.assertRaises(Exception):  # Replace with the appropriate exception
            Review.objects.create(**self.review_data)

    def test_delete_review_versions(self):
        review = Review.objects.create(**self.review_data)
        review.content = "This is an updated review."
        review.save()

        # Ensure a new version was created
        review_versions = ReviewVersion.objects.filter(review=review)
        self.assertEqual(review_versions.count(), 1)

        # Store the primary key of the review
        review_pk = review.pk

        review.delete()

        # Ensure all versions were deleted
        review_versions = ReviewVersion.objects.filter(review_id=review_pk)
        self.assertEqual(review_versions.count(), 0)


class ReviewVersionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.community = Community.objects.create(name="Test Community")
        self.review_data = {
            "article": self.article,
            "user": self.user,
            "community": self.community,
            "rating": 5,
            "subject": "Great Article",
            "content": "This is a great article. I learned a lot.",
        }
        self.review = Review.objects.create(**self.review_data)
        self.review_version_data = {
            "review": self.review,
            "rating": 5,
            "subject": "Great Article",
            "content": "This is a great article. I learned a lot.",
            "version": 1,
        }

    def test_create_review_version(self):
        review_version = ReviewVersion.objects.create(**self.review_version_data)
        self.assertEqual(review_version.review, self.review)
        self.assertEqual(review_version.rating, 5)
        self.assertEqual(review_version.subject, "Great Article")
        self.assertEqual(
            review_version.content, "This is a great article. I learned a lot."
        )
        self.assertEqual(review_version.version, 1)

    def test_review_version_str(self):
        review_version = ReviewVersion.objects.create(**self.review_version_data)
        expected_str = f"Version {review_version.version} of {self.review.subject}"
        self.assertEqual(str(review_version), expected_str)


# class ReviewCommentModelTest(TestCase):
#     def setUp(self):
#         self.user = User.objects.create_user(
#             username="testuser", email="testuser@example.com", password="password123"
#         )
#         self.article = Article.objects.create(
#             title="Test Article",
#             abstract="This is a test abstract.",
#             authors=["Author One", "Author Two"],
#             submission_type="Public",
#             submitter=self.user,
#             faqs=[],
#         )
#         self.community = Community.objects.create(name="Test Community")
#         self.review = Review.objects.create(
#             article=self.article,
#             user=self.user,
#             community=self.community,
#             rating=5,
#             subject="Great Article",
#             content="This is a great article. I learned a lot.",
#         )
#         self.review_version = ReviewVersion.objects.create(
#             review=self.review,
#             rating=5,
#             subject="Great Article",
#             content="This is a great article. I learned a lot.",
#             version=1,
#         )

#     def test_create_review_comment(self):
#         review_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a comment.",
#         )
#         self.assertEqual(review_comment.review, self.review)
#         self.assertEqual(review_comment.author, self.user)
#         self.assertEqual(review_comment.community, self.community)
#         self.assertEqual(review_comment.content, "This is a comment.")
#         self.assertIsNone(review_comment.rating)
#         self.assertFalse(review_comment.is_deleted)

#     def test_create_nested_review_comment(self):
#         parent_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a parent comment.",
#         )
#         child_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a child comment.",
#             parent=parent_comment,
#         )
#         self.assertEqual(child_comment.parent, parent_comment)

#     def test_exceed_maximum_comment_nesting_level(self):
#         parent_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a parent comment.",
#         )
#         child_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a child comment.",
#             parent=parent_comment,
#         )
#         grandchild_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a grandchild comment.",
#             parent=child_comment,
#         )

#         with self.assertRaises(ValueError):
#             great_grandchild_comment = ReviewComment.objects.create(
#                 review=self.review,
#                 author=self.user,
#                 community=self.community,
#                 content="This is a great-grandchild comment.",
#                 parent=grandchild_comment,
#             )

#     def test_get_anonymous_name(self):
#         review_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a comment.",
#         )
#         anonymous_name = review_comment.get_anonymous_name()
#         self.assertIsInstance(anonymous_name, str)
#         self.assertTrue(len(anonymous_name) > 0)

#     def test_is_deleted_field(self):
#         review_comment = ReviewComment.objects.create(
#             review=self.review,
#             author=self.user,
#             community=self.community,
#             content="This is a comment.",
#         )
#         self.assertFalse(review_comment.is_deleted)
#         review_comment.is_deleted = True
#         review_comment.save()
#         self.assertTrue(review_comment.is_deleted)


class ReviewCommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.community = Community.objects.create(name="Test Community")
        self.review = Review.objects.create(
            article=self.article,
            user=self.user,
            community=self.community,
            rating=5,
            subject="Great Article",
            content="This is a great article. I learned a lot.",
        )
        self.review_version = ReviewVersion.objects.create(
            review=self.review,
            rating=5,
            subject="Great Article",
            content="This is a great article. I learned a lot.",
            version=1,
        )

    def test_create_review_comment(self):
        review_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a comment.",
        )
        self.assertEqual(review_comment.review, self.review)
        self.assertEqual(review_comment.author, self.user)
        self.assertEqual(review_comment.community, self.community)
        self.assertEqual(review_comment.content, "This is a comment.")
        self.assertIsNone(review_comment.rating)
        self.assertFalse(review_comment.is_deleted)

    def test_create_nested_review_comment(self):
        parent_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a parent comment.",
        )
        child_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a child comment.",
            parent=parent_comment,
        )
        self.assertEqual(child_comment.parent, parent_comment)

    def test_exceed_maximum_comment_nesting_level(self):
        parent_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a parent comment.",
        )
        child_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a child comment.",
            parent=parent_comment,
        )
        grandchild_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a grandchild comment.",
            parent=child_comment,
        )

        with self.assertRaises(ValueError):
            ReviewComment.objects.create(
                review=self.review,
                author=self.user,
                community=self.community,
                content="This is a great-grandchild comment.",
                parent=grandchild_comment,
            )

    def test_get_anonymous_name(self):
        review_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a comment.",
        )
        anonymous_name = review_comment.get_anonymous_name()
        self.assertIsInstance(anonymous_name, str)
        self.assertTrue(len(anonymous_name) > 0)

    def test_is_deleted_field(self):
        review_comment = ReviewComment.objects.create(
            review=self.review,
            author=self.user,
            community=self.community,
            content="This is a comment.",
        )
        self.assertFalse(review_comment.is_deleted)
        review_comment.is_deleted = True
        review_comment.save()
        self.assertTrue(review_comment.is_deleted)


class ReactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.content_type = ContentType.objects.get_for_model(Article)
        self.reaction_data = {
            "user": self.user,
            "content_type": self.content_type,
            "object_id": self.article.id,
            "vote": Reaction.LIKE,
        }

    def test_create_reaction(self):
        reaction = Reaction.objects.create(**self.reaction_data)
        self.assertEqual(reaction.user, self.user)
        self.assertEqual(reaction.content_type, self.content_type)
        self.assertEqual(reaction.object_id, self.article.id)
        self.assertEqual(reaction.vote, Reaction.LIKE)

    def test_reaction_str(self):
        reaction = Reaction.objects.create(**self.reaction_data)
        expected_str = (
            f"{self.user.username} - {reaction.get_vote_display()} "
            f"on {reaction.content_object}"
        )
        self.assertEqual(str(reaction), expected_str)

    def test_unique_together_constraint(self):
        Reaction.objects.create(**self.reaction_data)
        with self.assertRaises(IntegrityError):
            Reaction.objects.create(**self.reaction_data)

    def test_change_vote(self):
        reaction = Reaction.objects.create(**self.reaction_data)
        reaction.vote = Reaction.DISLIKE
        reaction.save()
        self.assertEqual(reaction.vote, Reaction.DISLIKE)


class DiscussionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.community = Community.objects.create(name="Test Community")
        self.discussion_data = {
            "article": self.article,
            "author": self.user,
            "community": self.community,
            "topic": "Discussion Topic",
            "content": "This is the discussion content.",
        }

    def test_create_discussion(self):
        discussion = Discussion.objects.create(**self.discussion_data)
        self.assertEqual(discussion.article, self.article)
        self.assertEqual(discussion.author, self.user)
        self.assertEqual(discussion.community, self.community)
        self.assertEqual(discussion.topic, "Discussion Topic")
        self.assertEqual(discussion.content, "This is the discussion content.")
        self.assertIsNone(discussion.deleted_at)

    def test_get_anonymous_name(self):
        discussion = Discussion.objects.create(**self.discussion_data)
        anonymous_name = discussion.get_anonymous_name()
        self.assertIsInstance(anonymous_name, str)
        self.assertTrue(len(anonymous_name) > 0)

    def test_deleted_at_field(self):
        discussion = Discussion.objects.create(**self.discussion_data)
        self.assertIsNone(discussion.deleted_at)
        discussion.deleted_at = fake.date_time_this_year(tzinfo=None)
        discussion.save()
        self.assertIsNotNone(discussion.deleted_at)


class DiscussionCommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[],
        )
        self.community = Community.objects.create(name="Test Community")
        self.discussion = Discussion.objects.create(
            article=self.article,
            author=self.user,
            community=self.community,
            topic="Discussion Topic",
            content="This is the discussion content.",
        )
        self.discussion_comment_data = {
            "discussion": self.discussion,
            "author": self.user,
            "community": self.community,
            "content": "This is a comment.",
        }

    def test_create_discussion_comment(self):
        discussion_comment = DiscussionComment.objects.create(
            **self.discussion_comment_data
        )
        self.assertEqual(discussion_comment.discussion, self.discussion)
        self.assertEqual(discussion_comment.author, self.user)
        self.assertEqual(discussion_comment.community, self.community)
        self.assertEqual(discussion_comment.content, "This is a comment.")

    def test_get_anonymous_name(self):
        discussion_comment = DiscussionComment.objects.create(
            **self.discussion_comment_data
        )
        anonymous_name = discussion_comment.get_anonymous_name()
        self.assertIsInstance(anonymous_name, str)
        self.assertTrue(len(anonymous_name) > 0)

    def test_create_nested_discussion_comment(self):
        parent_comment = DiscussionComment.objects.create(
            **self.discussion_comment_data
        )
        child_comment = DiscussionComment.objects.create(
            discussion=self.discussion,
            author=self.user,
            community=self.community,
            content="This is a reply to the parent comment.",
            parent=parent_comment,
        )
        self.assertEqual(child_comment.parent, parent_comment)
