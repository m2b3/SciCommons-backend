from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from articles.models import Article
from communities.models import (
    Community,
    CommunityArticle,
    Invitation,
    JoinRequest,
    Membership,
)

User = get_user_model()


class CommunityModelTest(TestCase):

    def setUp(self):
        # Create users for testing
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="password123"
        )

        # Create a community
        self.community = Community.objects.create(
            name="Test Community",
            description="This is a test community",
            type=Community.PUBLIC,
            rules=["No spam", "Be respectful"],
            about={"mission": "To test"},
        )
        # Add user1 as an admin
        self.community.admins.add(self.user1)
        # Add user2 as a member through the Membership model
        Membership.objects.create(user=self.user2, community=self.community)

    def test_create_community(self):
        community = Community.objects.create(
            name="New Community",
            description="This is another test community",
            type=Community.HIDDEN,
        )
        self.assertEqual(community.name, "New Community")
        self.assertEqual(community.type, Community.HIDDEN)
        self.assertTrue(community.slug)

    def test_is_member(self):
        # Check if user2 is a member of the community
        self.assertTrue(self.community.is_member(self.user2))
        # Check if user1 (admin) is a member of the community
        self.assertFalse(self.community.is_member(self.user1))
        # Check if a non-member is not a member of the community
        user3 = User.objects.create_user(
            username="user3", email="user3@example.com", password="password123"
        )
        self.assertFalse(self.community.is_member(user3))

    def test_slug_creation(self):
        community = Community.objects.create(
            name="Community With Unique Name",
        )
        self.assertEqual(community.slug, "community-with-unique-name")

    def test_string_representation(self):
        self.assertEqual(str(self.community), self.community.name)

    def test_community_has_admins(self):
        self.assertIn(self.user1, self.community.admins.all())

    def test_community_has_members(self):
        self.assertIn(self.user2, self.community.members.all())


# class MembershipModelTest(TestCase):

#     def setUp(self):
#         # Create users for testing
#         self.user1 = User.objects.create_user(
#             username="user1", email="user1@example.com", password="password123"
#         )
#         self.user2 = User.objects.create_user(
#             username="user2", email="user2@example.com", password="password123"
#         )

#         # Create a community
#         self.community = Community.objects.create(
#             name="Test Community",
#             description="This is a test community",
#             type=Community.PUBLIC,
#             rules=["No spam", "Be respectful"],
#             about={"mission": "To test"},
#         )
#         # Add user1 as a member through the Membership model
#         self.membership1 = Membership.objects.create(
#             user=self.user1, community=self.community
#         )
#         # Add user2 as a member through the Membership model
#         self.membership2 = Membership.objects.create(
#             user=self.user2, community=self.community
#         )

#     def test_create_membership(self):
#         user3 = User.objects.create_user(
#             username="user3", email="user3@example.com", password="password123"
#         )
#         membership = Membership.objects.create(user=user3, community=self.community)
#         self.assertIn(user3, self.community.members.all())
#         self.assertTrue(
#             Membership.objects.filter(user=user3, community=self.community).exists()
#         )

#     def test_membership_auto_joined_at(self):
#         self.assertIsNotNone(self.membership1.joined_at)
#         self.assertIsNotNone(self.membership2.joined_at)

#     def test_membership_relationship(self):
#         # Check if user1 and user2 are members of the community
#         self.assertIn(self.user1, self.community.members.all())
#         self.assertIn(self.user2, self.community.members.all())
#         # Verify membership existence
#         self.assertTrue(
#             Membership.objects.filter(
#                 user=self.user1, community=self.community
#             ).exists()
#         )
#         self.assertTrue(
#             Membership.objects.filter(
#                 user=self.user2, community=self.community
#             ).exists()
#         )

#     def test_membership_deletion_on_user_deletion(self):
#         user1_id = self.user1.id
#         community_id = self.community.id
#         self.user1.delete()
#         self.assertFalse(
#             Membership.objects.filter(
#                 user_id=user1_id, community_id=community_id
#             ).exists()
#         )

#     def test_membership_deletion_on_community_deletion(self):
#         community_id = self.community.id
#         self.community.delete()
#         self.assertFalse(Membership.objects.filter(community_id=community_id).exists())


class MembershipModelTest(TestCase):
    def setUp(self):
        # Create users for testing
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="password123"
        )

        # Create a community
        self.community = Community.objects.create(
            name="Test Community",
            description="This is a test community",
            type=Community.PUBLIC,
            rules=["No spam", "Be respectful"],
            about={"mission": "To test"},
        )
        # Add user1 as a member through the Membership model
        self.membership1 = Membership.objects.create(
            user=self.user1, community=self.community
        )
        # Add user2 as a member through the Membership model
        self.membership2 = Membership.objects.create(
            user=self.user2, community=self.community
        )

    def test_create_membership(self):
        user3 = User.objects.create_user(
            username="user3", email="user3@example.com", password="password123"
        )
        Membership.objects.create(user=user3, community=self.community)
        self.assertIn(user3, self.community.members.all())
        self.assertTrue(
            Membership.objects.filter(user=user3, community=self.community).exists()
        )

    def test_membership_auto_joined_at(self):
        self.assertIsNotNone(self.membership1.joined_at)
        self.assertIsNotNone(self.membership2.joined_at)

    def test_membership_relationship(self):
        # Check if user1 and user2 are members of the community
        self.assertIn(self.user1, self.community.members.all())
        self.assertIn(self.user2, self.community.members.all())
        # Verify membership existence
        self.assertTrue(
            Membership.objects.filter(
                user=self.user1, community=self.community
            ).exists()
        )
        self.assertTrue(
            Membership.objects.filter(
                user=self.user2, community=self.community
            ).exists()
        )

    def test_membership_deletion_on_user_deletion(self):
        user1_id = self.user1.id
        community_id = self.community.id
        self.user1.delete()
        self.assertFalse(
            Membership.objects.filter(
                user_id=user1_id, community_id=community_id
            ).exists()
        )

    def test_membership_deletion_on_community_deletion(self):
        community_id = self.community.id
        self.community.delete()
        self.assertFalse(Membership.objects.filter(community_id=community_id).exists())


class InvitationModelTest(TestCase):
    def setUp(self):
        """
        Set up initial data for the tests, including creating a user and a community.

        Args:
            None

        Returns:
            None
        """
        # Create a user for testing
        self.user = User.objects.create_user(
            username="user1", email="user1@example.com", password="password123"
        )

        # Create a community for testing
        self.community = Community.objects.create(
            name="Test Community",
            description="This is a test community",
            type=Community.PUBLIC,
            rules=["No spam", "Be respectful"],
            about={"mission": "To test"},
        )

    def test_create_invitation_with_email(self):
        """
        Test creating an invitation with an email.

        Args:
            None

        Returns:
            None
        """
        # Create an invitation with an email address
        invitation = Invitation.objects.create(
            community=self.community,
            email="invitee@example.com",
            status=Invitation.PENDING,
        )

        # Assert that the invitation was created with the correct community and email
        self.assertEqual(invitation.community, self.community)
        self.assertEqual(invitation.email, "invitee@example.com")
        self.assertEqual(invitation.status, Invitation.PENDING)
        self.assertIsNotNone(
            invitation.invited_at
        )  # Check that the invited_at timestamp is set
        self.assertEqual(
            str(invitation),
            f"Invitation for invitee@example.com to {self.community.name}",
        )  # Check string representation

    def test_create_invitation_with_username(self):
        """
        Test creating an invitation with a username.

        Args:
            None

        Returns:
            None
        """
        # Create an invitation with a username
        invitation = Invitation.objects.create(
            community=self.community, username="invitee_user", status=Invitation.PENDING
        )

        # Assert that the invitation was created with the correct community and username
        self.assertEqual(invitation.community, self.community)
        self.assertEqual(invitation.username, "invitee_user")
        self.assertEqual(invitation.status, Invitation.PENDING)
        self.assertIsNotNone(
            invitation.invited_at
        )  # Check that the invited_at timestamp is set
        self.assertEqual(
            str(invitation), f"Invitation for invitee_user to {self.community.name}"
        )  # Check string representation

    def test_create_invitation_without_email_and_username(self):
        """
        Test creating an invitation without an email or username.

        Args:
            None

        Returns:
            None
        """
        # Create an invitation without an email or username
        invitation = Invitation.objects.create(
            community=self.community, status=Invitation.PENDING
        )

        # Assert that the invitation was created with the correct community and status
        self.assertEqual(invitation.community, self.community)
        self.assertEqual(invitation.status, Invitation.PENDING)
        self.assertIsNotNone(
            invitation.invited_at
        )  # Check that the invited_at timestamp is set
        self.assertEqual(
            str(invitation), f"Invitation to {self.community.name}"
        )  # Check string representation

    def test_update_invitation_status(self):
        """
        Test updating the status of an invitation.

        Args:
            None

        Returns:
            None
        """
        # Create an invitation and update its status
        invitation = Invitation.objects.create(
            community=self.community,
            email="invitee@example.com",
            status=Invitation.PENDING,
        )
        invitation.status = Invitation.ACCEPTED
        invitation.save()

        # Assert that the invitation's status was updated correctly
        self.assertEqual(invitation.status, Invitation.ACCEPTED)


class JoinRequestModelTest(TestCase):

    def setUp(self):
        """
        Set up initial data for the tests, including creating users and a community.

        Args:
            None

        Returns:
            None
        """
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="password123"
        )

        self.community = Community.objects.create(
            name="Test Community",
            description="This is a test community",
            type=Community.PUBLIC,
            rules=["No spam", "Be respectful"],
            about={"mission": "To test"},
        )

    def test_create_join_request(self):
        """
        Test creating a join request.

        Args:
            None

        Returns:
            None
        """
        join_request = JoinRequest.objects.create(
            user=self.user1, community=self.community, status=JoinRequest.PENDING
        )
        self.assertEqual(join_request.user, self.user1)
        self.assertEqual(join_request.community, self.community)
        self.assertEqual(join_request.status, JoinRequest.PENDING)
        self.assertIsNotNone(join_request.requested_at)
        self.assertIsNone(join_request.rejection_timestamp)
        self.assertEqual(
            str(join_request), f"{self.user1} requesting to join {self.community}"
        )

    def test_approve_join_request(self):
        """
        Test approving a join request.

        Args:
            None

        Returns:
            None
        """
        join_request = JoinRequest.objects.create(
            user=self.user1, community=self.community, status=JoinRequest.PENDING
        )
        join_request.status = JoinRequest.APPROVED
        join_request.save()
        self.assertEqual(join_request.status, JoinRequest.APPROVED)
        self.assertIsNone(join_request.rejection_timestamp)

    def test_reject_join_request(self):
        """
        Test rejecting a join request and setting rejection timestamp.

        Args:
            None

        Returns:
            None
        """
        join_request = JoinRequest.objects.create(
            user=self.user2, community=self.community, status=JoinRequest.PENDING
        )
        join_request.status = JoinRequest.REJECTED
        join_request.rejection_timestamp = timezone.now()
        join_request.save()
        self.assertEqual(join_request.status, JoinRequest.REJECTED)
        self.assertIsNotNone(join_request.rejection_timestamp)

    def test_pending_join_request(self):
        """
        Test creating a join request with pending status.

        Args:
            None

        Returns:
            None
        """
        join_request = JoinRequest.objects.create(
            user=self.user1, community=self.community, status=JoinRequest.PENDING
        )
        self.assertEqual(join_request.status, JoinRequest.PENDING)
        self.assertIsNone(join_request.rejection_timestamp)


class CommunityArticleTestCase(TestCase):
    def setUp(self):
        # Create a sample user, community, and article for testing
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="testpass"
        )
        self.community = Community.objects.create(name="Test Community")
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test article.",
            authors=["Author 1", "Author 2"],
            submission_type="Public",
            submitter=self.user,
            faqs=["FAQ 1", "FAQ 2"],
        )

    def test_community_article_creation(self):
        # Create a CommunityArticle instance
        community_article = CommunityArticle.objects.create(
            article=self.article, community=self.community
        )

        # Check if the CommunityArticle instance is created
        self.assertIsInstance(community_article, CommunityArticle)

        # Check if the default status is 'submitted'
        self.assertEqual(community_article.status, "submitted")

        # Check if submitted_at is set automatically
        self.assertIsNotNone(community_article.submitted_at)

        # Check if published_at is None initially
        self.assertIsNone(community_article.published_at)

    def test_community_article_status_change(self):
        community_article = CommunityArticle.objects.create(
            article=self.article, community=self.community
        )

        # Change status to 'approved'
        community_article.status = "approved"
        community_article.save()
        self.assertEqual(community_article.status, "approved")

        # Change status to 'published' and set published_at
        community_article.status = "published"
        community_article.published_at = timezone.now()
        community_article.save()
        self.assertEqual(community_article.status, "published")
        self.assertIsNotNone(community_article.published_at)

        # Change status to 'rejected' and ensure published_at remains the same
        old_published_at = community_article.published_at
        community_article.status = "rejected"
        community_article.save()
        self.assertEqual(community_article.status, "rejected")
        self.assertEqual(community_article.published_at, old_published_at)

    def test_published_at_updates_correctly(self):
        community_article = CommunityArticle.objects.create(
            article=self.article, community=self.community
        )

        # Initially published_at should be None
        self.assertIsNone(community_article.published_at)

        # Set status to 'published' and set published_at
        now = timezone.now()
        community_article.status = "published"
        community_article.published_at = now
        community_article.save()

        # Check if published_at is updated correctly
        self.assertEqual(community_article.published_at, now)

        # Change status to another state and check published_at does not change
        community_article.status = "under_review"
        community_article.save()
        self.assertEqual(community_article.published_at, now)
