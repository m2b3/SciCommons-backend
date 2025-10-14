#!/usr/bin/env python3
"""
Tornado Server for Real-time Discussions
Handles long-polling, queue management, and event delivery
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import redis.asyncio as redis
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
from decouple import config
from tornado.log import enable_pretty_logging

from myapp.feature_flags import (
    HEARTBEAT_INTERVAL_SECONDS,
    MAX_EVENTS_PER_QUEUE,
    POLL_TIMEOUT_SECONDS,
    QUEUE_TTL_MINUTES,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = config("REALTIME_REDIS_URL", default="redis://localhost:6379/3")
TORNADO_PORT = int(config("TORNADO_PORT", default="8888"))

# Global state
user_queues: Dict[str, Dict] = {}  # queue_id -> queue_data
user_communities: Dict[str, Set[int]] = {}  # queue_id -> set of community_ids
user_to_queue: Dict[int, str] = {}  # user_id -> queue_id (to prevent duplicates)
pending_polls: Dict[str, tornado.concurrent.Future] = {}  # queue_id -> Future
global_event_id = 0
redis_client: Optional[redis.Redis] = None


class QueueManager:
    """Manages user queues and their lifecycle"""

    @staticmethod
    def create_queue(
        queue_id: str, user_id: int, community_ids: Set[int], last_event_id: int
    ) -> Dict:
        """Create a new queue for a user"""
        queue_data = {
            "queue_id": queue_id,
            "user_id": user_id,
            "events": [],
            "last_event_id": last_event_id,
            "created_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow(),
            "community_ids": community_ids,
        }

        user_queues[queue_id] = queue_data
        user_communities[queue_id] = community_ids
        user_to_queue[user_id] = queue_id  # Track user -> queue mapping

        logger.info(
            f"Created queue {queue_id} for user {user_id} with communities {community_ids}"
        )
        return queue_data

    @staticmethod
    def get_existing_queue(user_id: int) -> Optional[Dict]:
        """Check if user already has an active queue"""
        existing_queue_id = user_to_queue.get(user_id)
        if existing_queue_id and existing_queue_id in user_queues:
            return user_queues[existing_queue_id]

        # Clean up stale mapping if queue no longer exists
        if existing_queue_id:
            user_to_queue.pop(user_id, None)

        return None

    @staticmethod
    def update_heartbeat(queue_id: str) -> bool:
        """Update the heartbeat timestamp for a queue"""
        if queue_id in user_queues:
            old_heartbeat = user_queues[queue_id]["last_heartbeat"]
            user_queues[queue_id]["last_heartbeat"] = datetime.utcnow()
            logger.debug(
                f"Updated heartbeat for queue {queue_id} (was {old_heartbeat})"
            )
            return True
        else:
            logger.warning(
                f"Attempted to update heartbeat for non-existent queue {queue_id}"
            )
            return False

    @staticmethod
    def add_event_to_queues(event: Dict, target_community_ids: Set[int]):
        """Add an event to all relevant user queues, excluding the author"""
        global global_event_id
        global_event_id += 1

        event["event_id"] = global_event_id
        event["timestamp"] = datetime.utcnow().isoformat()

        # Get the user to exclude (the author of the event)
        exclude_user_id = event.get("exclude_user_id")

        added_to_queues = 0
        excluded_author = False

        for queue_id, queue_data in user_queues.items():
            user_id = queue_data["user_id"]

            # Skip if this is the author's queue
            if exclude_user_id and user_id == exclude_user_id:
                excluded_author = True
                logger.debug(
                    f"Excluding author (user {user_id}) from receiving their own event"
                )
                continue

            # Check if user belongs to any of the target communities
            user_community_ids = user_communities.get(queue_id, set())
            if target_community_ids.intersection(user_community_ids):
                # Add event to queue
                queue_data["events"].append(event)

                # Limit queue size
                if len(queue_data["events"]) > MAX_EVENTS_PER_QUEUE:
                    queue_data["events"] = queue_data["events"][-MAX_EVENTS_PER_QUEUE:]

                added_to_queues += 1

                # Notify pending poll if exists
                if queue_id in pending_polls:
                    future = pending_polls.pop(queue_id)
                    if not future.done():
                        future.set_result(True)

        author_info = (
            f" (excluded author: user {exclude_user_id})" if excluded_author else ""
        )
        logger.info(
            f"Added event {global_event_id} to {added_to_queues} queues for communities {target_community_ids}{author_info}"
        )

    @staticmethod
    def get_events_since(queue_id: str, last_event_id: int) -> List[Dict]:
        """Get events for a queue since a specific event ID"""
        if queue_id not in user_queues:
            return []

        queue_data = user_queues[queue_id]
        events = []

        for event in queue_data["events"]:
            if event["event_id"] > last_event_id:
                events.append(event)

        return events

    @staticmethod
    def cleanup_expired_queues():
        """Remove expired queues based on TTL with race condition protection"""
        current_time = datetime.utcnow()
        ttl_threshold = current_time - timedelta(minutes=QUEUE_TTL_MINUTES)

        # Add 30-second buffer to prevent race conditions with active polls
        buffer_threshold = current_time - timedelta(
            minutes=QUEUE_TTL_MINUTES, seconds=30
        )

        expired_queues = []
        active_queues_info = []

        for queue_id, queue_data in user_queues.items():
            last_heartbeat = queue_data["last_heartbeat"]
            user_id = queue_data["user_id"]
            age_minutes = (current_time - last_heartbeat).total_seconds() / 60

            if last_heartbeat < buffer_threshold:
                # Only cleanup queues that are well past the TTL (with buffer)
                expired_queues.append((queue_id, user_id, age_minutes))
            else:
                active_queues_info.append((queue_id, user_id, age_minutes))

        # Log current queue status for debugging
        if active_queues_info:
            logger.debug(f"Active queues: {len(active_queues_info)} queues")
            for queue_id, user_id, age in active_queues_info:
                logger.debug(
                    f"  Queue {queue_id[:8]}... (user {user_id}): {age:.1f} min old"
                )

        # Cleanup expired queues
        for queue_id, user_id, age_minutes in expired_queues:
            logger.info(
                f"Expiring queue {queue_id[:8]}... (user {user_id}) - idle for {age_minutes:.1f} minutes"
            )

            user_queues.pop(queue_id, None)
            user_communities.pop(queue_id, None)
            user_to_queue.pop(user_id, None)  # Clean up user mapping

            # Cancel pending poll if exists
            if queue_id in pending_polls:
                future = pending_polls.pop(queue_id)
                if not future.done():
                    future.set_result(False)
                logger.debug(
                    f"Cancelled pending poll for expired queue {queue_id[:8]}..."
                )

        if expired_queues:
            logger.info(f"Cleaned up {len(expired_queues)} expired queues")
        elif len(user_queues) > 0:
            logger.debug(
                f"No queues to cleanup. {len(user_queues)} active queues remaining."
            )


class HealthHandler(tornado.web.RequestHandler):
    """Health check endpoint"""

    def get(self):
        self.write(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "active_queues": len(user_queues),
                "pending_polls": len(pending_polls),
                "user_mappings": len(user_to_queue),
                "users_with_queues": list(user_to_queue.keys()),
            }
        )


class RegisterHandler(tornado.web.RequestHandler):
    """Handle queue registration requests from Django"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header(
            "Access-Control-Allow-Headers",
            "x-requested-with, content-type, authorization",
        )
        self.set_header(
            "Access-Control-Allow-Methods", "POST, GET, PUT, DELETE, OPTIONS"
        )

    def options(self):
        self.set_status(204)
        self.finish()

    def post(self):
        try:
            data = json.loads(self.request.body)
            user_id = data.get("user_id")
            community_ids = set(data.get("community_ids", []))

            if not user_id or not community_ids:
                self.set_status(400)
                self.write({"error": "user_id and community_ids are required"})
                return

            # Check if user already has an active queue
            existing_queue = QueueManager.get_existing_queue(user_id)

            if existing_queue:
                # Update heartbeat and community IDs for existing queue
                QueueManager.update_heartbeat(existing_queue["queue_id"])

                # Update community IDs if they've changed
                existing_queue["community_ids"] = community_ids
                user_communities[existing_queue["queue_id"]] = community_ids

                logger.info(
                    f"Returning existing queue {existing_queue['queue_id']} for user {user_id}"
                )

                self.write(
                    {
                        "queue_id": existing_queue["queue_id"],
                        "last_event_id": global_event_id,
                    }
                )
                return

            # Generate unique queue ID for new queue
            queue_id = str(uuid.uuid4())

            # Create new queue
            queue_data = QueueManager.create_queue(
                queue_id=queue_id,
                user_id=user_id,
                community_ids=community_ids,
                last_event_id=global_event_id,
            )

            self.write({"queue_id": queue_id, "last_event_id": global_event_id})

        except json.JSONDecodeError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Error in RegisterHandler: {e}")
            self.set_status(500)
            self.write({"error": "Internal server error"})


class HeartbeatHandler(tornado.web.RequestHandler):
    """Handle heartbeat requests to keep queues alive"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header(
            "Access-Control-Allow-Headers",
            "x-requested-with, content-type, authorization",
        )
        self.set_header(
            "Access-Control-Allow-Methods", "POST, GET, PUT, DELETE, OPTIONS"
        )

    def options(self):
        self.set_status(204)
        self.finish()

    def post(self):
        try:
            data = json.loads(self.request.body)
            queue_id = data.get("queue_id")

            if not queue_id:
                self.set_status(400)
                self.write({"error": "queue_id is required"})
                return

            if QueueManager.update_heartbeat(queue_id):
                self.write({"status": "ok"})
            else:
                self.set_status(404)
                self.write({"error": "Queue not found"})

        except json.JSONDecodeError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Error in HeartbeatHandler: {e}")
            self.set_status(500)
            self.write({"error": "Internal server error"})


class PollHandler(tornado.web.RequestHandler):
    """Handle long-polling requests for events"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header(
            "Access-Control-Allow-Headers",
            "x-requested-with, content-type, authorization",
        )
        self.set_header(
            "Access-Control-Allow-Methods", "POST, GET, PUT, DELETE, OPTIONS"
        )

    def options(self):
        self.set_status(204)
        self.finish()

    async def get(self):
        queue_id = self.get_argument("queue_id", None)
        last_event_id = int(self.get_argument("last_event_id", 0))

        if not queue_id:
            self.set_status(400)
            self.write({"error": "queue_id is required"})
            return

        if queue_id not in user_queues:
            self.set_status(404)
            self.write({"error": "Queue not found"})
            return

        # Auto-heartbeat: Update last_heartbeat on every poll request
        QueueManager.update_heartbeat(queue_id)

        # Check if there are already new events
        events = QueueManager.get_events_since(queue_id, last_event_id)

        if events:
            # Return immediately if we have events
            self.write({"events": events, "last_event_id": global_event_id})
            return

        # No events, start long polling
        future = tornado.concurrent.Future()
        pending_polls[queue_id] = future

        try:
            # Wait for new events or timeout
            await asyncio.wait_for(future, timeout=POLL_TIMEOUT_SECONDS)

            # Get new events
            events = QueueManager.get_events_since(queue_id, last_event_id)
            self.write({"events": events, "last_event_id": global_event_id})

        except asyncio.TimeoutError:
            # Timeout reached, return empty events
            self.write({"events": [], "last_event_id": global_event_id})
        except Exception as e:
            logger.error(f"Error in PollHandler: {e}")
            self.set_status(500)
            self.write({"error": "Internal server error"})
        finally:
            # Clean up pending poll
            pending_polls.pop(queue_id, None)


async def redis_event_listener():
    """Listen for events from Redis and distribute to queues"""
    global redis_client

    try:
        redis_client = redis.from_url(REDIS_URL)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("discussion_events")

        logger.info(
            f"Started Redis event listener on channel 'discussion_events' with Redis URL: {REDIS_URL}"
        )

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    logger.info(f"Received Redis message: {message['data']}")
                    event_data = json.loads(message["data"])

                    # Extract community IDs from the event
                    community_ids = set()
                    if "community_id" in event_data:
                        community_ids.add(event_data["community_id"])
                    if "community_ids" in event_data:
                        community_ids.update(event_data["community_ids"])

                    if community_ids:
                        logger.info(
                            f"Processing event for communities {community_ids}: {event_data.get('type', 'unknown')}"
                        )
                        QueueManager.add_event_to_queues(event_data, community_ids)
                    else:
                        logger.warning(
                            f"Event missing community information: {event_data}"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode Redis message: {e}")
                except Exception as e:
                    logger.error(f"Error processing Redis event: {e}")
            elif message["type"] == "subscribe":
                logger.info(
                    f"Successfully subscribed to Redis channel: {message['channel']}"
                )

    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        # Retry connection after 5 seconds
        await asyncio.sleep(5)
        tornado.ioloop.IOLoop.current().add_callback(redis_event_listener)


def cleanup_queues_periodic():
    """Periodic cleanup of expired queues"""
    QueueManager.cleanup_expired_queues()

    # Schedule next cleanup
    tornado.ioloop.IOLoop.current().call_later(60, cleanup_queues_periodic)


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    tornado.ioloop.IOLoop.current().stop()
    sys.exit(0)


def make_app():
    """Create the Tornado application"""
    return tornado.web.Application(
        [
            (r"/health", HealthHandler),
            (r"/realtime/register", RegisterHandler),
            (r"/realtime/heartbeat", HeartbeatHandler),
            (r"/realtime/poll", PollHandler),
        ],
        debug=False,
    )


if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Enable pretty logging
    enable_pretty_logging()

    # Create and start the application
    app = make_app()
    app.listen(TORNADO_PORT, "0.0.0.0")

    logger.info(f"Tornado server starting on port {TORNADO_PORT}")
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Queue TTL: {QUEUE_TTL_MINUTES} minutes")

    # Start the event loop
    ioloop = tornado.ioloop.IOLoop.current()

    # Start Redis listener
    ioloop.add_callback(redis_event_listener)

    # Start periodic cleanup
    ioloop.call_later(60, cleanup_queues_periodic)

    # Start the server
    logger.info("Tornado server is ready")
    ioloop.start()
