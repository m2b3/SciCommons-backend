"""
Real-time API endpoints for SciCommons
Handles queue registration and heartbeat for long-polling
"""

import logging
from typing import List, Optional

from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from myapp.realtime import RealtimeQueueManager, get_user_community_ids
from myapp.schemas import (
    Message,
    RealtimeHeartbeatOut,
    RealtimeRegisterOut,
    RealtimeStatusOut,
)
from users.auth import JWTAuth

logger = logging.getLogger(__name__)

router = Router(tags=["Real-time"])


@router.post(
    "/register",
    response={200: RealtimeRegisterOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def register_queue(request):
    """
    Register a new queue for real-time updates

    Returns:
        - queue_id: Unique identifier for this user's queue
        - last_event_id: Current event ID to start polling from
    """
    try:
        user = request.auth

        # Get user's private community memberships
        community_ids = list(get_user_community_ids(user))

        if not community_ids:
            return 400, {"message": "User is not a member of any private communities"}

        # Register queue with Tornado
        result = RealtimeQueueManager.register_user_queue(user.id, community_ids)

        if result is None:
            return 500, {"message": "Failed to register queue with real-time server"}

        logger.info(
            f"Registered queue for user {user.id} with communities {community_ids}"
        )

        return {
            "queue_id": result["queue_id"],
            "last_event_id": result["last_event_id"],
            "communities": community_ids,
        }

    except Exception as e:
        logger.error(f"Error in register_queue: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/heartbeat",
    response={200: RealtimeHeartbeatOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def heartbeat(request, queue_id: str):
    """
    Send heartbeat to keep queue alive

    Args:
        queue_id: The queue ID to send heartbeat for
    """
    try:
        user = request.auth

        # Send heartbeat to Tornado
        success = RealtimeQueueManager.send_heartbeat(queue_id)

        if not success:
            return 404, {"message": "Queue not found or expired"}

        logger.debug(f"Heartbeat sent for queue {queue_id} by user {user.id}")

        return {"message": "Heartbeat successful"}

    except Exception as e:
        logger.error(f"Error in heartbeat: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.get(
    "/status",
    response={200: RealtimeStatusOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_realtime_status(request):
    """
    Get real-time system status for the current user

    Returns status information about the real-time system
    """
    try:
        user = request.auth

        # Get user's community memberships
        community_ids = list(get_user_community_ids(user))

        return {
            "user_id": user.id,
            "communities": community_ids,
            "realtime_enabled": len(community_ids) > 0,
            "tornado_url": "/realtime",  # Frontend will use relative URL
        }

    except Exception as e:
        logger.error(f"Error in get_realtime_status: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
