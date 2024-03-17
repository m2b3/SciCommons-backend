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

    def test_unique_admin_per_community(self):
        with self.assertRaises(IntegrityError):
            # Attempt to create another admin for the same community
            CommunityMember.objects.create(
                community=self.community,
                user=self.another_user,
                is_admin=True
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
