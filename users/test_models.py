from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Notification
from articles.models import Article
from posts.models import Post
from communities.models import Community
from django.utils.timezone import now, timedelta
from users.models import Hashtag ,HashtagRelation, Reputation,Bookmark
from django.db import IntegrityError
from django.contrib.contenttypes.models import ContentType


User = get_user_model()

class UserManagerTest(TestCase):
    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "password123",
        }
        self.superuser_data = {
            "username": "admin",
            "email": "admin@example.com",
            "password": "adminpassword",
        }

    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.username, self.user_data["username"])
        self.assertEqual(user.email, self.user_data["email"])
        self.assertTrue(user.check_password(self.user_data["password"]))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_create_user_without_email(self):
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                username="testuser",
                email="",
                password="password123"
            )
        self.assertEqual(str(context.exception), "The Email must be set")

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(**self.superuser_data)
        self.assertEqual(superuser.username, self.superuser_data["username"])
        self.assertEqual(superuser.email, self.superuser_data["email"])
        self.assertTrue(superuser.check_password(self.superuser_data["password"]))
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_active)

    def test_create_superuser_without_is_staff(self):
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="adminpassword",
                is_staff=False
            )
        self.assertEqual(str(context.exception), "Superuser must have is_staff=True.")

    def test_create_superuser_without_is_superuser(self):
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="adminpassword",
                is_superuser=False
            )
        self.assertEqual(str(context.exception), "Superuser must have is_superuser=True.")



class UserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "password123",
            "bio": "This is a test bio.",
            "pubMed_url": "http://example.com/pubmed",
            "google_scholar_url": "http://example.com/scholar",
            "home_page_url": "http://example.com",
            "linkedin_url": "http://linkedin.com/in/testuser",
            "github_url": "http://github.com/testuser",
            "academic_statuses": [
                {"academic_email": "testuser@university.edu", "start_year": 2020, "end_year": 2024}
            ],
        }

    def test_create_user_with_additional_fields(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.username, self.user_data["username"])
        self.assertEqual(user.email, self.user_data["email"])
        self.assertTrue(user.check_password(self.user_data["password"]))
        self.assertEqual(user.bio, self.user_data["bio"])
        self.assertEqual(user.pubMed_url, self.user_data["pubMed_url"])
        self.assertEqual(user.google_scholar_url, self.user_data["google_scholar_url"])
        self.assertEqual(user.home_page_url, self.user_data["home_page_url"])
        self.assertEqual(user.linkedin_url, self.user_data["linkedin_url"])
        self.assertEqual(user.github_url, self.user_data["github_url"])
        self.assertEqual(user.academic_statuses, self.user_data["academic_statuses"])

    def test_user_default_values(self):
        user = User.objects.create_user(
            username="testuser2",
            email="testuser2@example.com",
            password="password123"
        )
        self.assertIsNone(user.profile_pic_url.name)
        self.assertIsNone(user.bio)
        self.assertIsNone(user.pubMed_url)
        self.assertIsNone(user.google_scholar_url)
        self.assertIsNone(user.home_page_url)
        self.assertIsNone(user.linkedin_url)
        self.assertIsNone(user.github_url)
        self.assertEqual(user.academic_statuses, [])

    def test_user_str(self):
        user = User.objects.create_user(
            username="testuser3",
            email="testuser3@example.com",
            password="password123"
        )
        self.assertEqual(str(user), user.username)

    def test_user_int(self):
        user = User.objects.create_user(
            username="testuser4",
            email="testuser4@example.com",
            password="password123"
        )
        self.assertEqual(int(user), user.id)


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            abstract="This is a test abstract.",
            authors=["Author One", "Author Two"],
            submission_type="Public",
            submitter=self.user,
            faqs=[]
        )
        self.post = Post.objects.create(
            author=self.user,
            title="Test Post",
            content="This is a test post content.",
        )
        self.community = Community.objects.create(name="Test Community")
        self.notification_data = {
            "user": self.user,
            "category": "articles",
            "notification_type": "article_commented",
            "message": "Your article has a new comment.",
            "article": self.article,
        }

    def test_create_notification(self):
        notification = Notification.objects.create(**self.notification_data)
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.category, self.notification_data["category"])
        self.assertEqual(notification.notification_type, self.notification_data["notification_type"])
        self.assertEqual(notification.message, self.notification_data["message"])
        self.assertEqual(notification.article, self.article)
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.expires_at)

    def test_notification_str(self):
        notification = Notification.objects.create(**self.notification_data)
        expected_str = (
            f"{notification.category.title()} - "
            f"{notification.get_notification_type_display()} - "
            f"{notification.message}"
        )
        self.assertEqual(str(notification), expected_str)

    def test_set_expiration(self):
        notification = Notification.objects.create(**self.notification_data)
        days = 5
        notification.set_expiration(days)
        expected_expiration = now() + timedelta(days=days)
        # Allow some flexibility for time differences
        self.assertTrue(abs((notification.expires_at - expected_expiration).total_seconds()) < 1)

    def test_notification_with_post(self):
        self.notification_data.update({
            "category": "posts",
            "notification_type": "post_replied",
            "message": "Your post has a new reply.",
            "post": self.post,
            "article": None,  # Ensure article is None
        })
        notification = Notification.objects.create(**self.notification_data)
        self.assertEqual(notification.post, self.post)
        self.assertIsNone(notification.article)



class HashtagModelTest(TestCase):
    def setUp(self):
        self.hashtag_data = {
            "name": "testhashtag",
        }

    def test_create_hashtag(self):
        hashtag = Hashtag.objects.create(**self.hashtag_data)
        self.assertEqual(hashtag.name, self.hashtag_data["name"])

    def test_unique_hashtag_name(self):
        Hashtag.objects.create(**self.hashtag_data)
        with self.assertRaises(IntegrityError):
            Hashtag.objects.create(name="testhashtag")


class HashtagRelationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )
        self.post = Post.objects.create(
            author=self.user,
            title="Test Post",
            content="This is a test post content.",
        )
        self.hashtag = Hashtag.objects.create(name="testhashtag")
        self.content_type = ContentType.objects.get_for_model(Post)
        self.hashtag_relation_data = {
            "hashtag": self.hashtag,
            "content_type": self.content_type,
            "object_id": self.post.id,
        }

    def test_create_hashtag_relation(self):
        hashtag_relation = HashtagRelation.objects.create(**self.hashtag_relation_data)
        self.assertEqual(hashtag_relation.hashtag, self.hashtag)
        self.assertEqual(hashtag_relation.content_type, self.content_type)
        self.assertEqual(hashtag_relation.object_id, self.post.id)
        self.assertEqual(hashtag_relation.content_object, self.post)

    def test_hashtag_relation_str(self):
        hashtag_relation = HashtagRelation.objects.create(**self.hashtag_relation_data)
        expected_str = f"# {self.hashtag.name}"
        self.assertEqual(str(hashtag_relation), expected_str)

    def test_unique_together_constraint(self):
        HashtagRelation.objects.create(**self.hashtag_relation_data)
        with self.assertRaises(IntegrityError):
            HashtagRelation.objects.create(**self.hashtag_relation_data)



class ReputationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )
        self.reputation = Reputation.objects.create(user=self.user)

    def test_create_reputation(self):
        self.assertEqual(self.reputation.user, self.user)
        self.assertEqual(self.reputation.score, 0)
        self.assertEqual(self.reputation.level, "Novice")

    def test_add_reputation(self):
        self.reputation.add_reputation("SUBMIT_ARTICLE")
        self.assertEqual(self.reputation.score, Reputation.SUBMIT_ARTICLE)
        self.assertEqual(self.reputation.level, "Novice")
        
        self.reputation.add_reputation("CREATE_COMMUNITY")
        self.assertEqual(self.reputation.score, Reputation.SUBMIT_ARTICLE + Reputation.CREATE_COMMUNITY)
        self.assertEqual(self.reputation.level, "Novice")

        self.reputation.add_reputation("SUBMIT_ARTICLE")
        self.reputation.add_reputation("SUBMIT_ARTICLE")
        self.reputation.add_reputation("SUBMIT_ARTICLE")
        self.assertEqual(self.reputation.score, Reputation.SUBMIT_ARTICLE * 4 + Reputation.CREATE_COMMUNITY)
        self.reputation.add_reputation("SUBMIT_ARTICLE")
        self.assertEqual(self.reputation.score, Reputation.SUBMIT_ARTICLE * 5 + Reputation.CREATE_COMMUNITY)
        self.assertEqual(self.reputation.level, "Contributor")

    def test_update_level(self):
        self.reputation.score = 200
        self.reputation.update_level()
        self.assertEqual(self.reputation.level, "Expert")

        self.reputation.score = 600
        self.reputation.update_level()
        self.assertEqual(self.reputation.level, "Master")

    def test_next_level(self):
        self.reputation.score = 45
        self.reputation.update_level()
        next_level, points_needed = self.reputation.next_level
        self.assertEqual(next_level, "Contributor")
        self.assertEqual(points_needed, 5)

        self.reputation.score = 210
        self.reputation.update_level()
        next_level, points_needed = self.reputation.next_level
        self.assertEqual(next_level, "Master")
        self.assertEqual(points_needed, 290)

    def test_get_top_users(self):
        user2 = User.objects.create_user(
            username="testuser2",
            email="testuser2@example.com",
            password="password123"
        )
        user3 = User.objects.create_user(
            username="testuser3",
            email="testuser3@example.com",
            password="password123"
        )
        reputation2 = Reputation.objects.create(user=user2, score=300)
        reputation3 = Reputation.objects.create(user=user3, score=150)

        top_users = Reputation.get_top_users(limit=2)
        self.assertEqual(len(top_users), 2)
        self.assertEqual(top_users[0], reputation2)
        self.assertEqual(top_users[1], reputation3)

    def test_calculate_community_reputation(self):
        community = Community.objects.create(name="Test Community")
        community.members.add(self.user)
        user2 = User.objects.create_user(
            username="testuser2",
            email="testuser2@example.com",
            password="password123"
        )
        community.members.add(user2)
        Reputation.objects.create(user=user2, score=300)

        total_reputation = Reputation.calculate_community_reputation(community)
        self.assertEqual(total_reputation, 300)

    def test_str(self):
        self.assertEqual(str(self.reputation), f"{self.user.username} - Novice (0 points)")



class BookmarkModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )
        self.post = Post.objects.create(
            author=self.user,
            title="Test Post",
            content="This is a test post content.",
        )
        self.content_type = ContentType.objects.get_for_model(Post)
        self.bookmark_data = {
            "user": self.user,
            "content_type": self.content_type,
            "object_id": self.post.id,
        }

    def test_create_bookmark(self):
        bookmark = Bookmark.objects.create(**self.bookmark_data)
        self.assertEqual(bookmark.user, self.user)
        self.assertEqual(bookmark.content_type, self.content_type)
        self.assertEqual(bookmark.object_id, self.post.id)
        self.assertEqual(bookmark.content_object, self.post)

    def test_bookmark_str(self):
        bookmark = Bookmark.objects.create(**self.bookmark_data)
        expected_str = f"{self.user.username} - Bookmark for {self.post}"
        self.assertEqual(str(bookmark), expected_str)

    def test_unique_together_constraint(self):
        Bookmark.objects.create(**self.bookmark_data)
        with self.assertRaises(IntegrityError):
            Bookmark.objects.create(**self.bookmark_data)
