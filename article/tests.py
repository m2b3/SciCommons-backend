from django.test import TestCase

from article.models import Article, ArticleReviewer, ArticleBlockedUser, ArticleModerator, Author, CommentBase
from community.models import Community, OfficialReviewer, Moderator
from user.models import User


# Create your tests here.

class ArticleModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            subtitle='Test Subtitle',
            description='Test Description',
            location='Test Location',
            user=self.user
        )

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

    def test_article_creation(self):
        article = Article.objects.get(id='test_article')
        self.assertEqual(article.article_name, 'Test Article')
        self.assertEqual(article.keywords, 'test, article')
        self.assertEqual(article.authorstring, 'Test Author')
        self.assertEqual(article.status, 'public')

    def test_article_str(self):
        self.assertEqual(str(self.article), 'Test Article')


class ArticleReviewerModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            subtitle='Test Subtitle',
            description='Test Description',
            location='Test Location',
            user=self.user
        )

        # Create an official reviewer
        self.official_reviewer = OfficialReviewer.objects.create(
            User=self.user,
            Official_Reviewer_name='John Doe',
            community=self.community
        )

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create an article reviewer
        self.article_reviewer = ArticleReviewer.objects.create(
            article=self.article,
            officialreviewer=self.official_reviewer
        )

    def test_article_reviewer_creation(self):
        article_reviewer = ArticleReviewer.objects.get(id=self.article_reviewer.id)
        self.assertEqual(article_reviewer.article, self.article)
        self.assertEqual(article_reviewer.officialreviewer, self.official_reviewer)

    def test_article_reviewer_str(self):
        self.assertEqual(str(self.article_reviewer), 'Test Article')


class ArticleBlockedUserModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create an article blocked user
        self.article_blocked_user = ArticleBlockedUser.objects.create(
            article=self.article,
            user=self.user
        )

    def test_article_blocked_user_creation(self):
        article_blocked_user = ArticleBlockedUser.objects.get(id=self.article_blocked_user.id)
        self.assertEqual(article_blocked_user.article, self.article)
        self.assertEqual(article_blocked_user.user, self.user)


class ArticleModeratorModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            subtitle='Test Subtitle',
            description='Test Description',
            location='Test Location',
            user=self.user
        )

        # Create a moderator
        self.moderator = Moderator.objects.create(
            user=self.user,
            community=self.community
        )

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create an article moderator
        self.article_moderator = ArticleModerator.objects.create(
            article=self.article,
            moderator=self.moderator
        )

    def test_article_moderator_creation(self):
        article_moderator = ArticleModerator.objects.get(id=self.article_moderator.id)
        self.assertEqual(article_moderator.article, self.article)
        self.assertEqual(article_moderator.moderator, self.moderator)

    def test_article_moderator_str(self):
        self.assertEqual(str(self.article_moderator), 'Test Article')


class AuthorModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create an author
        self.author = Author.objects.create(
            article=self.article,
            User=self.user
        )

    def test_author_creation(self):
        author = Author.objects.get(id=self.author.id)
        self.assertEqual(author.article, self.article)
        self.assertEqual(author.User, self.user)

    def test_author_str(self):
        self.assertEqual(str(self.author), 'testuser')

    def test_unique_together_constraint(self):
        # Attempt to create another Author with the same article and User
        with self.assertRaises(Exception):
            Author.objects.create(
                article=self.article,
                User=self.user
            )


class CommentBaseModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create an article
        self.article = Article.objects.create(
            id='test_article',
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create a comment
        self.comment = CommentBase.objects.create(
            User=self.user,
            article=self.article,
            Comment='This is a test comment.',
            rating=4,
            confidence=3,
            Title='Test Comment',
            tag='public',
            comment_type='publiccomment',
            Type='comment'
        )

    def test_comment_creation(self):
        comment = CommentBase.objects.get(id=self.comment.id)
        self.assertEqual(comment.User, self.user)
        self.assertEqual(comment.article, self.article)
        self.assertEqual(comment.Comment, 'This is a test comment.')
        self.assertEqual(comment.rating, 4)
        self.assertEqual(comment.confidence, 3)
        self.assertEqual(comment.Title, 'Test Comment')
        self.assertEqual(comment.tag, 'public')
        self.assertEqual(comment.comment_type, 'publiccomment')
        self.assertEqual(comment.Type, 'comment')