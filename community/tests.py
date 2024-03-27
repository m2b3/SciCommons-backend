from django.test import TestCase

from article.models import Article
from community.models import Community, CommunityMember, UnregisteredUser, OfficialReviewer
from user.models import User


# Create your tests here.

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
        self.another_user = User.objects.create_user(username='anotheruser', email='anotheruser@example.com',
                                                     password='password')

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
