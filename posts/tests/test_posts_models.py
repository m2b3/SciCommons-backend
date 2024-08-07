from django.contrib.auth import get_user_model
from django.test import TestCase
from faker import Faker

from articles.models import Reaction
from users.models import Hashtag, HashtagRelation

from ..models import Comment, Post

User = get_user_model()
fake = Faker()


class PostModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.post_data = {
            "author": self.user,
            "title": "Test Post",
            "content": "This is a test post content.",
        }

    def test_create_post(self):
        post = Post.objects.create(**self.post_data)
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.title, "Test Post")
        self.assertEqual(post.content, "This is a test post content.")
        self.assertFalse(post.is_deleted)

    def test_post_str(self):
        post = Post.objects.create(**self.post_data)
        self.assertEqual(str(post), post.title)

    def test_is_deleted_field(self):
        post = Post.objects.create(**self.post_data)
        self.assertFalse(post.is_deleted)
        post.is_deleted = True
        post.save()
        self.assertTrue(post.is_deleted)

    def test_reactions_relation(self):
        post = Post.objects.create(**self.post_data)
        reaction = Reaction.objects.create(
            user=self.user, content_object=post, vote=Reaction.LIKE
        )
        self.assertIn(reaction, post.reactions.all())

    def test_hashtags_relation(self):
        post = Post.objects.create(**self.post_data)
        hashtag = Hashtag.objects.create(name="testhashtag")
        hashtag_relation = HashtagRelation.objects.create(
            content_object=post, hashtag=hashtag
        )
        self.assertIn(hashtag_relation, post.hashtags.all())


class CommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.post = Post.objects.create(
            author=self.user,
            title="Test Post",
            content="This is a test post content.",
        )
        self.comment_data = {
            "author": self.user,
            "post": self.post,
            "content": "This is a test comment.",
        }

    def test_create_comment(self):
        comment = Comment.objects.create(**self.comment_data)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.post, self.post)
        self.assertEqual(comment.content, "This is a test comment.")
        self.assertFalse(comment.is_deleted)

    def test_comment_str(self):
        comment = Comment.objects.create(**self.comment_data)
        expected_str = f"Comment by {self.user.username} on {self.post.title}"
        self.assertEqual(str(comment), expected_str)

    def test_is_deleted_field(self):
        comment = Comment.objects.create(**self.comment_data)
        self.assertFalse(comment.is_deleted)
        comment.is_deleted = True
        comment.save()
        self.assertTrue(comment.is_deleted)

    def test_reactions_relation(self):
        comment = Comment.objects.create(**self.comment_data)
        reaction = Reaction.objects.create(
            user=self.user, content_object=comment, vote=Reaction.LIKE
        )
        self.assertIn(reaction, comment.reactions.all())

    def test_create_nested_comment(self):
        parent_comment = Comment.objects.create(**self.comment_data)
        child_comment = Comment.objects.create(
            author=self.user,
            post=self.post,
            content="This is a reply to the parent comment.",
            parent=parent_comment,
        )
        self.assertEqual(child_comment.parent, parent_comment)
