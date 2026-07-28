import json
import unittest
from datetime import datetime, timedelta

from tornado.testing import AsyncHTTPTestCase

import tornado_server


def reset_tornado_state():
    """Reset the in-memory realtime state so tests remain isolated."""
    tornado_server.user_queues.clear()
    tornado_server.user_communities.clear()
    tornado_server.user_to_queue.clear()
    tornado_server.pending_polls.clear()
    tornado_server.global_event_id = 0


class QueueManagerRoutingTests(unittest.TestCase):
    def setUp(self):
        reset_tornado_state()
        tornado_server.QueueManager.create_queue("queue-1", 1, {10}, 0)
        tornado_server.QueueManager.create_queue("queue-2", 2, {10}, 0)
        tornado_server.QueueManager.create_queue("queue-3", 3, {20}, 0)

    def tearDown(self):
        reset_tornado_state()

    def assert_queue_event_count(self, queue_id, expected_count):
        self.assertEqual(
            len(tornado_server.user_queues[queue_id]["events"]),
            expected_count,
        )

    def test_absent_subscriber_filter_broadcasts_to_community_members(self):
        tornado_server.QueueManager.add_event_to_queues(
            {"type": "community-update", "data": {}},
            target_community_ids={10},
        )

        self.assert_queue_event_count("queue-1", 1)
        self.assert_queue_event_count("queue-2", 1)
        self.assert_queue_event_count("queue-3", 0)

    def test_empty_subscriber_filter_delivers_to_nobody(self):
        tornado_server.QueueManager.add_event_to_queues(
            {"type": "discussion-update", "data": {"subscriber_ids": []}},
            target_community_ids={10},
        )

        self.assert_queue_event_count("queue-1", 0)
        self.assert_queue_event_count("queue-2", 0)
        self.assert_queue_event_count("queue-3", 0)

    def test_subscriber_filter_only_delivers_to_listed_community_members(self):
        tornado_server.QueueManager.add_event_to_queues(
            {"type": "discussion-update", "data": {"subscriber_ids": [1, 3]}},
            target_community_ids={10},
        )

        self.assert_queue_event_count("queue-1", 1)
        self.assert_queue_event_count("queue-2", 0)
        self.assert_queue_event_count("queue-3", 0)

    def test_author_is_excluded_even_when_subscribed(self):
        tornado_server.QueueManager.add_event_to_queues(
            {
                "type": "discussion-update",
                "exclude_user_id": 1,
                "data": {"subscriber_ids": [1, 2]},
            },
            target_community_ids={10},
        )

        self.assert_queue_event_count("queue-1", 0)
        self.assert_queue_event_count("queue-2", 1)
        self.assert_queue_event_count("queue-3", 0)

    def test_direct_user_routing_takes_priority_over_subscriber_filter(self):
        tornado_server.QueueManager.add_event_to_queues(
            {"type": "notification", "data": {"subscriber_ids": []}},
            target_community_ids={10},
            target_user_ids={2},
        )

        self.assert_queue_event_count("queue-1", 0)
        self.assert_queue_event_count("queue-2", 1)
        self.assert_queue_event_count("queue-3", 0)


class QueueManagerTimestampTests(unittest.TestCase):
    def setUp(self):
        reset_tornado_state()

    def tearDown(self):
        reset_tornado_state()

    def test_queue_and_heartbeat_timestamps_are_aware_utc(self):
        queue = tornado_server.QueueManager.create_queue("queue-1", 1, {10}, 0)

        self.assertEqual(queue["created_at"].utcoffset(), timedelta(0))
        self.assertEqual(queue["last_heartbeat"].utcoffset(), timedelta(0))

        tornado_server.QueueManager.update_heartbeat("queue-1")
        self.assertEqual(
            tornado_server.user_queues["queue-1"]["last_heartbeat"].utcoffset(),
            timedelta(0),
        )

    def test_event_timestamp_is_iso_formatted_aware_utc(self):
        tornado_server.QueueManager.create_queue("queue-1", 1, {10}, 0)
        event = {"type": "community-update", "data": {}}

        tornado_server.QueueManager.add_event_to_queues(
            event,
            target_community_ids={10},
        )

        timestamp = datetime.fromisoformat(event["timestamp"])
        self.assertEqual(timestamp.utcoffset(), timedelta(0))


class TornadoHandlerTests(AsyncHTTPTestCase):
    def setUp(self):
        reset_tornado_state()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        reset_tornado_state()

    def get_app(self):
        return tornado_server.make_app()

    def test_poll_rejects_non_integer_last_event_id(self):
        response = self.fetch("/realtime/poll?queue_id=queue-1&last_event_id=not-an-integer")

        self.assertEqual(response.code, 400)
        self.assertEqual(
            json.loads(response.body),
            {"error": "last_event_id must be an integer"},
        )

    def test_health_timestamp_is_aware_utc(self):
        response = self.fetch("/health")

        self.assertEqual(response.code, 200)
        timestamp = datetime.fromisoformat(json.loads(response.body)["timestamp"])
        self.assertEqual(timestamp.utcoffset(), timedelta(0))
