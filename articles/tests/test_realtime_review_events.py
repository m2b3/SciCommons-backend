"""Focused tests for the six realtime review/review-comment event contracts (PR 165).

PR 165 added `publish_review_created/updated/deleted` and
`publish_review_comment_created/updated/deleted` to `myapp/realtime.py` -- six externally
visible event contracts that the frontend consumes by name and by payload shape -- with no
tests of any kind. These pin down:

  * the exact event names the frontend switches on,
  * the payload keys it reads (including the `comment` alias it falls back to),
  * author exclusion,
  * nested reply metadata,
  * pseudonym serialization,
  * and which community types publish at all.

`publish_event` ends in `get_redis_client().publish("discussion_events", json.dumps(event))`,
so the assertions read the JSON actually handed to Redis rather than mocking the publisher.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from articles.models import AnonymousIdentity, Article, Review, ReviewComment
from articles.review_api import router as review_router
from communities.models import Community, CommunityArticle, Membership
from myapp.realtime import EventTypes, RealtimeEventPublisher

User = get_user_model()


class RealtimeEventCaptureMixin:
    """Captures the JSON payloads published to the `discussion_events` Redis channel."""

    def start_capture(self):
        self.redis_client = MagicMock()
        patcher = patch("myapp.realtime.get_redis_client", return_value=self.redis_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def published_events(self):
        events = []
        for call in self.redis_client.publish.call_args_list:
            channel, raw = call.args
            self.assertEqual(channel, "discussion_events")
            events.append(json.loads(raw))
        return events

    def single_event(self):
        events = self.published_events()
        self.assertEqual(len(events), 1, f"expected exactly one event, got {len(events)}")
        return events[0]


class ReviewEventFixtureMixin:
    def build_world(self, community_type=Community.PRIVATE):
        self.author = User.objects.create_user(
            username="review_author", email="author@example.com", password="password123"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@example.com", password="password123"
        )
        # Communities always have a creator-admin in practice; an admin-less community makes
        # the notification path fail on a null user_id, which is unrelated to these assertions.
        self.admin = User.objects.create_user(
            username="community_admin", email="admin@example.com", password="password123"
        )

        self.community = Community.objects.create(name="private-lab", type=community_type)
        self.community.admins.add(self.admin)
        Membership.objects.create(user=self.author, community=self.community)
        Membership.objects.create(user=self.commenter, community=self.community)

        self.article = Article.objects.create(
            title="A paper worth reviewing",
            abstract="Abstract text.",
            authors=[{"value": "Someone", "label": "Someone"}],
            submission_type="Private",
            submitter=self.admin,
        )
        self.community_article = CommunityArticle.objects.create(
            article=self.article,
            community=self.community,
            status=CommunityArticle.PUBLISHED,
        )
        self.review = Review.objects.create(
            article=self.article,
            user=self.author,
            community=self.community,
            community_article=self.community_article,
            rating=4,
            subject="Solid methodology",
            content="The methods section is convincing.",
        )


class ReviewPublisherPayloadTests(RealtimeEventCaptureMixin, ReviewEventFixtureMixin, TestCase):
    """Event names and payload shapes for the three review-level publishers."""

    def setUp(self):
        self.start_capture()
        self.build_world()

    def test_review_created_event_name_and_payload(self):
        RealtimeEventPublisher.publish_review_created(self.review, {self.community.id})

        event = self.single_event()
        self.assertEqual(event["type"], "new_review")
        self.assertEqual(event["type"], EventTypes.NEW_REVIEW)
        self.assertEqual(event["community_ids"], [self.community.id])

        data = event["data"]
        self.assertEqual(data["review_id"], self.review.id)
        self.assertEqual(data["article_id"], self.article.id)
        self.assertEqual(data["community_id"], self.community.id)
        # The frontend resolves the review body from data.review (useRealtime.tsx).
        self.assertEqual(data["review"]["id"], self.review.id)
        self.assertEqual(data["review"]["subject"], "Solid methodology")

    def test_review_updated_and_deleted_event_names(self):
        RealtimeEventPublisher.publish_review_updated(self.review, {self.community.id})
        RealtimeEventPublisher.publish_review_deleted(self.review, {self.community.id})

        names = [event["type"] for event in self.published_events()]
        self.assertEqual(names, ["updated_review", "deleted_review"])
        self.assertEqual(names, [EventTypes.UPDATED_REVIEW, EventTypes.DELETED_REVIEW])

    def test_review_events_exclude_their_author(self):
        for publish in (
            RealtimeEventPublisher.publish_review_created,
            RealtimeEventPublisher.publish_review_updated,
            RealtimeEventPublisher.publish_review_deleted,
        ):
            with self.subTest(publisher=publish.__name__):
                self.redis_client.publish.reset_mock()
                publish(self.review, {self.community.id})
                self.assertEqual(self.single_event()["exclude_user_id"], self.author.id)

    def test_pseudonymous_review_serializes_the_pseudonym_not_the_username(self):
        AnonymousIdentity.objects.create(
            user=self.author,
            article=self.article,
            community=self.community,
            fake_name="Curious_Otter_4821",
        )
        self.review.is_pseudonymous = True
        self.review.save()

        RealtimeEventPublisher.publish_review_created(self.review, {self.community.id})

        review_data = self.single_event()["data"]["review"]
        self.assertTrue(review_data["is_pseudonymous"])
        self.assertEqual(review_data["user"]["username"], "Curious_Otter_4821")
        self.assertNotIn("review_author", json.dumps(review_data))

    def test_subscriber_ids_is_absent_pending_the_transport_port(self):
        """Pins a known gap rather than letting it drift silently.

        `tornado_server.py` on this branch has no `subscriber_ids` support -- it routes on
        community/user targeting only -- so the field is deliberately omitted here. When the
        absent/empty/populated contract lands, all six publishers should populate it (reusing
        `get_discussion_subscribers`) and this test should be inverted.
        """
        RealtimeEventPublisher.publish_review_created(self.review, {self.community.id})
        self.assertNotIn("subscriber_ids", self.single_event()["data"])


class ReviewCommentPublisherPayloadTests(
    RealtimeEventCaptureMixin, ReviewEventFixtureMixin, TestCase
):
    """Event names, payload shapes and reply metadata for the three comment publishers."""

    def setUp(self):
        self.start_capture()
        self.build_world()
        self.comment = ReviewComment.objects.create(
            review=self.review,
            author=self.commenter,
            community=self.community,
            content="Could you clarify the sample size?",
        )

    def test_comment_created_event_name_and_payload(self):
        RealtimeEventPublisher.publish_review_comment_created(self.comment, {self.community.id})

        event = self.single_event()
        self.assertEqual(event["type"], "new_review_comment")
        self.assertEqual(event["type"], EventTypes.NEW_REVIEW_COMMENT)

        data = event["data"]
        self.assertEqual(data["comment_id"], self.comment.id)
        self.assertEqual(data["review_id"], self.review.id)
        self.assertEqual(data["article_id"], self.article.id)
        self.assertEqual(data["community_id"], self.community.id)
        # The frontend reads `review_comment` but falls back to `comment`; both must be sent.
        self.assertEqual(data["review_comment"]["id"], self.comment.id)
        self.assertEqual(data["comment"]["id"], self.comment.id)

    def test_comment_updated_and_deleted_event_names(self):
        RealtimeEventPublisher.publish_review_comment_updated(self.comment, {self.community.id})
        RealtimeEventPublisher.publish_review_comment_deleted(self.comment, {self.community.id})

        names = [event["type"] for event in self.published_events()]
        self.assertEqual(names, ["updated_review_comment", "deleted_review_comment"])

    def test_comment_events_exclude_their_author(self):
        RealtimeEventPublisher.publish_review_comment_created(self.comment, {self.community.id})
        self.assertEqual(self.single_event()["exclude_user_id"], self.commenter.id)

    def test_top_level_comment_reports_no_parent(self):
        RealtimeEventPublisher.publish_review_comment_created(self.comment, {self.community.id})

        data = self.single_event()["data"]
        self.assertIsNone(data["parent_id"])
        self.assertFalse(data["is_reply"])

    def test_reply_carries_parent_metadata(self):
        reply = ReviewComment.objects.create(
            review=self.review,
            parent=self.comment,
            author=self.author,
            community=self.community,
            content="It was 120 participants.",
        )

        RealtimeEventPublisher.publish_review_comment_created(reply, {self.community.id})

        data = self.single_event()["data"]
        self.assertEqual(data["parent_id"], self.comment.id)
        self.assertTrue(data["is_reply"])
        self.assertEqual(data["comment_id"], reply.id)

    def test_subscriber_ids_is_absent_pending_the_transport_port(self):
        RealtimeEventPublisher.publish_review_comment_created(self.comment, {self.community.id})
        self.assertNotIn("subscriber_ids", self.single_event()["data"])


class ReviewEventCommunityGateTests(RealtimeEventCaptureMixin, ReviewEventFixtureMixin, TestCase):
    """Which community types publish, exercised through the HTTP endpoint.

    The `type == "private"` condition lives at the call sites in `articles/review_api.py`,
    not inside the publishers, so it can only be verified by going through the endpoint.
    """

    def setUp(self):
        self.start_capture()
        self.client = TestClient(review_router)

    def auth_headers(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"Authorization": f"Bearer {token}"}

    def post_review(self, community, user):
        return self.client.post(
            f"/{self.article.id}/reviews/",
            json={"rating": 5, "subject": "Clear and useful", "content": "Well argued."},
            query_params={"community_id": community.id},
            headers=self.auth_headers(user),
        )

    def test_private_community_publishes_new_review(self):
        self.build_world(community_type=Community.PRIVATE)

        response = self.post_review(self.community, self.commenter)

        self.assertEqual(response.status_code, 201, response.content)
        review_events = [e for e in self.published_events() if e["type"] == EventTypes.NEW_REVIEW]
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0]["data"]["article_id"], self.article.id)

    def test_public_community_publishes_nothing(self):
        self.build_world(community_type=Community.PUBLIC)

        response = self.post_review(self.community, self.commenter)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual([e for e in self.published_events() if e["type"] == EventTypes.NEW_REVIEW], [])

    def test_hidden_community_publishes_nothing_by_decision(self):
        """Hidden communities are excluded deliberately, not by oversight.

        `DiscussionSubscription` covers private *and* hidden community articles
        (articles/models.py), so hidden could reasonably publish too. Keeping the
        private-only gate is the decision taken for PR 165; this test records it so a future
        change to include hidden is a conscious one that updates this assertion.
        """
        self.build_world(community_type=Community.HIDDEN)

        response = self.post_review(self.community, self.commenter)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual([e for e in self.published_events() if e["type"] == EventTypes.NEW_REVIEW], [])
