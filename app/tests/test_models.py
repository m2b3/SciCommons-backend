from django.test import TestCase
from ..models import *
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError


class UserManagerTest(TestCase):

    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertTrue(user.check_password('password'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpassword')
        self.assertEqual(admin_user.username, 'admin')
        self.assertEqual(admin_user.email, 'admin@example.com')
        self.assertTrue(admin_user.check_password('adminpassword'))
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

class UserModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password',
            pubmed='123456',
            google_scholar='scholar123',
            institute='Test Institute',
            email_notify=True,
            email_verified=False
        )

    def test_user_creation(self):
        user = User.objects.get(username='testuser')
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.pubmed, '123456')
        self.assertEqual(user.google_scholar, 'scholar123')
        self.assertEqual(user.institute, 'Test Institute')
        self.assertTrue(user.email_notify)
        self.assertFalse(user.email_verified)

    # This test passes only if the aws credentials are set in the environment
    # def test_user_profile_pic(self):
    #     # Create a simple image file
    #     image = SimpleUploadedFile(
    #         name='test_image.jpg',
    #         content=b'some image content',
    #         content_type='image/jpeg'
    #     )
    #     self.user.profile_pic_url = image
    #     self.user.save()

    #     user = User.objects.get(username='testuser')
    #     self.assertTrue(user.profile_pic_url.name.endswith('test_image.jpg'))

class UserActivityModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a user activity
        self.user_activity = UserActivity.objects.create(
            user=self.user,
            action='Test Action'
        )

    def test_user_activity_creation(self):
        user_activity = UserActivity.objects.get(id=self.user_activity.id)
        self.assertEqual(user_activity.user, self.user)
        self.assertEqual(user_activity.action, 'Test Action')

    def test_user_activity_str(self):
        self.assertEqual(str(self.user_activity), 'testuser-Test Action')
        
class EmailVerifyModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create an EmailVerify instance
        self.email_verify = EmailVerify.objects.create(
            user=self.user,
            otp=123456
        )

    def test_email_verify_creation(self):
        email_verify = EmailVerify.objects.get(id=self.email_verify.id)
        self.assertEqual(email_verify.user, self.user)
        self.assertEqual(email_verify.otp, 123456)

    def test_email_verify_str(self):
        self.assertEqual(str(self.email_verify), str(self.email_verify.id))

class ForgetPasswordModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a forget password record
        self.forget_password = ForgetPassword.objects.create(
            user=self.user,
            otp=123456
        )

    def test_forget_password_creation(self):
        forget_password = ForgetPassword.objects.get(id=self.forget_password.id)
        self.assertEqual(forget_password.user, self.user)
        self.assertEqual(forget_password.otp, 123456)

    def test_forget_password_str(self):
        self.assertEqual(str(self.forget_password), str(self.forget_password.id))

class CommunityModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            subtitle='Test Subtitle',
            description='Test Description',
            location='Test Location',
            github='https://github.com/test',
            email='test@example.com',
            website='https://www.test.com',
            user=self.user
        )

    def test_community_creation(self):
        community = Community.objects.get(id=self.community.id)
        self.assertEqual(community.Community_name, 'Test Community')
        self.assertEqual(community.subtitle, 'Test Subtitle')
        self.assertEqual(community.description, 'Test Description')
        self.assertEqual(community.location, 'Test Location')
        self.assertEqual(community.github, 'https://github.com/test')
        self.assertEqual(community.email, 'test@example.com')
        self.assertEqual(community.website, 'https://www.test.com')
        self.assertEqual(community.user, self.user)

    def test_community_str(self):
        self.assertEqual(str(self.community), 'Test Community')

class CommunityMemberModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create another user
        self.another_user = User.objects.create_user(username='anotheruser', email='anotheruser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            user=self.user
        )

        # Create a community member
        self.community_member = CommunityMember.objects.create(
            community=self.community,
            user=self.user,
            is_reviewer=False,
            is_moderator=False,
            is_admin=True
        )

    def test_community_member_creation(self):
        community_member = CommunityMember.objects.get(id=self.community_member.id)
        self.assertEqual(community_member.community, self.community)
        self.assertEqual(community_member.user, self.user)
        self.assertFalse(community_member.is_reviewer)
        self.assertFalse(community_member.is_moderator)
        self.assertTrue(community_member.is_admin)

    def test_community_member_str(self):
        self.assertEqual(str(self.community_member), f'{self.user} - {self.community}')

    # Todo: Rewrite this test
    # def test_unique_admin_per_community(self):
    #     with self.assertRaises(IntegrityError):
    #         # Attempt to create another admin for the same community
    #         CommunityMember.objects.create(
    #             community=self.community,
    #             user=self.another_user,
    #             is_admin=True
    #         )

class UnregisteredUserModelTest(TestCase):

    def setUp(self):
        # Create an article
        self.article = Article.objects.create(
            article_name='Test Article',
            keywords='test, article',
            authorstring='Test Author',
            status='public'
        )

        # Create an unregistered user
        self.unregistered_user = UnregisteredUser.objects.create(
            article=self.article,
            fullName='John Doe',
            email='johndoe@example.com'
        )

    def test_unregistered_user_creation(self):
        unregistered_user = UnregisteredUser.objects.get(id=self.unregistered_user.id)
        self.assertEqual(unregistered_user.article, self.article)
        self.assertEqual(unregistered_user.fullName, 'John Doe')
        self.assertEqual(unregistered_user.email, 'johndoe@example.com')

class OfficialReviewerModelTest(TestCase):

    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')

        # Create a community
        self.community = Community.objects.create(
            Community_name='Test Community',
            subtitle='Test Subtitle',
            description='Test Description',
            location='Test Location',
            github='https://github.com/test',
            email='test@example.com',
            website='https://www.test.com',
            user=self.user
        )

        # Create an official reviewer
        self.official_reviewer = OfficialReviewer.objects.create(
            User=self.user,
            Official_Reviewer_name='John Doe',
            community=self.community
        )

    def test_official_reviewer_creation(self):
        official_reviewer = OfficialReviewer.objects.get(id=self.official_reviewer.id)
        self.assertEqual(official_reviewer.User, self.user)
        self.assertEqual(official_reviewer.Official_Reviewer_name, 'John Doe')
        self.assertEqual(official_reviewer.community, self.community)

    def test_official_reviewer_str(self):
        self.assertEqual(str(self.official_reviewer), 'testuser')

    def test_unique_together_constraint(self):
        # Attempt to create another OfficialReviewer with the same User and community
        with self.assertRaises(Exception):
            OfficialReviewer.objects.create(
                User=self.user,
                Official_Reviewer_name='Jane Doe',
                community=self.community
            )

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
