"""
Flags API for managing user-specific entity state flags.

This module provides generic batch endpoints for:
- GET: Check which entities have a specific flag set
- POST: Add flags to entities
- DELETE: Remove flags from entities

Design principles:
- Presence-based: Row exists = flag is set, no row = flag not set
- Batch operations: All endpoints accept multiple entity IDs
- Generic: Same endpoints work for any flag type and entity type
"""

import logging
from typing import List

from ninja import Router, Schema
from ninja.errors import HttpError

from articles.models import Discussion, DiscussionComment, UserFlag
from myapp.schemas import EntityType, FlagType
from users.auth import JWTAuth

logger = logging.getLogger(__name__)

router = Router(tags=["Flags"])


# ============================================================================
# Schemas
# ============================================================================


class FlagRequestIn(Schema):
    """
    Request schema for flag operations (GET/POST/DELETE).

    All operations use the same request format for consistency.
    """

    flag_type: FlagType
    entity_type: EntityType
    entity_ids: List[int]


class FlagGetOut(Schema):
    """Response schema for GET - returns which entity IDs have the flag set"""

    flagged_entity_ids: List[int]


class FlagModifyOut(Schema):
    """Response schema for POST/DELETE - returns affected entity details"""

    flag_type: FlagType
    entity_type: EntityType
    entity_ids: List[int]


# ============================================================================
# Helper Functions
# ============================================================================


def validate_flag_type(flag_type: str) -> None:
    """Validate that the flag type is supported"""
    if flag_type not in UserFlag.VALID_FLAG_TYPES:
        raise HttpError(
            400,
            f"Invalid flag_type '{flag_type}'. Must be one of: {', '.join(UserFlag.VALID_FLAG_TYPES)}",
        )


def validate_entity_type(entity_type: str) -> None:
    """Validate that the entity type is supported"""
    if entity_type not in UserFlag.VALID_ENTITY_TYPES:
        raise HttpError(
            400,
            f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(UserFlag.VALID_ENTITY_TYPES)}",
        )


def authorize_entity_access(user, entity_type: str, entity_ids: List[int]) -> List[int]:
    """
    Authorize user access to entities and return only accessible entity IDs.

    For discussions/comments in private communities, user must be a member.
    Returns the subset of entity_ids that the user can access.
    """
    if not entity_ids:
        return []

    if entity_type == "discussion":
        # Get discussions and check community membership
        discussions = Discussion.objects.filter(id__in=entity_ids).select_related(
            "community"
        )
        accessible_ids = []
        for discussion in discussions:
            # If no community or public community, allow access
            # If private community, check membership
            if not discussion.community or discussion.community.is_member(user):
                accessible_ids.append(discussion.id)
        return accessible_ids

    elif entity_type == "comment":
        # Get comments and check community membership via discussion
        comments = DiscussionComment.objects.filter(id__in=entity_ids).select_related(
            "discussion__community"
        )
        accessible_ids = []
        for comment in comments:
            community = comment.discussion.community
            if not community or community.is_member(user):
                accessible_ids.append(comment.id)
        return accessible_ids

    elif entity_type == "notification":
        # For notifications, user can only access their own
        # (notifications will be user-specific when implemented)
        # For now, allow all - actual filtering happens at flag level (user FK)
        return list(entity_ids)

    # Default: return all (for future entity types, add authorization logic)
    return list(entity_ids)


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/",
    response=FlagGetOut,
    auth=JWTAuth(),
    summary="Get flags for entities",
    description="Check which entities have a specific flag set for the authenticated user.",
)
def get_flags(
    request,
    flag_type: FlagType,
    entity_type: EntityType,
    entity_ids: str,  # Comma-separated list of IDs (query params can't be arrays easily)
):
    """
    Get which entity IDs have a specific flag set.

    Returns only the entity IDs from the request that have the flag set.
    Useful for batch checking read/unread status, pinned items, etc.

    Args:
        flag_type: Type of flag to check (e.g., "unread")
        entity_type: Type of entity (e.g., "discussion", "comment")
        entity_ids: Comma-separated list of entity IDs (e.g., "1,2,3")
    """
    user = request.auth

    # Validate inputs
    validate_flag_type(flag_type)
    validate_entity_type(entity_type)

    # Parse entity_ids from comma-separated string
    try:
        parsed_entity_ids = [
            int(id.strip()) for id in entity_ids.split(",") if id.strip()
        ]
    except ValueError:
        from ninja.errors import HttpError

        raise HttpError(400, "entity_ids must be comma-separated integers")

    if not parsed_entity_ids:
        return FlagGetOut(flagged_entity_ids=[])

    # Authorize access to entities
    accessible_ids = authorize_entity_access(user, entity_type, parsed_entity_ids)

    if not accessible_ids:
        return FlagGetOut(flagged_entity_ids=[])

    # Get flagged entity IDs
    flagged_ids = UserFlag.objects.get_flagged_entity_ids(
        user_id=user.id,
        flag_type=flag_type,
        entity_type=entity_type,
        entity_ids=accessible_ids,
    )

    return FlagGetOut(flagged_entity_ids=list(flagged_ids))


@router.post(
    "/",
    response=FlagModifyOut,
    auth=JWTAuth(),
    summary="Add flags to entities",
    description="Add a flag to multiple entities for the authenticated user.",
)
def add_flags(request, payload: FlagRequestIn):
    """
    Add a flag to multiple entities.

    Creates flag entries for the specified entities. If a flag already exists
    for an entity, it's ignored (idempotent operation).
    """
    user = request.auth

    # Validate inputs
    validate_flag_type(payload.flag_type)
    validate_entity_type(payload.entity_type)

    if not payload.entity_ids:
        return FlagModifyOut(
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_ids=[],
        )

    # Authorize access to entities
    accessible_ids = authorize_entity_access(
        user, payload.entity_type, payload.entity_ids
    )

    if not accessible_ids:
        return FlagModifyOut(
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_ids=[],
        )

    # Add flags for each entity
    affected_entity_ids = []
    for entity_id in accessible_ids:
        flags = UserFlag.objects.bulk_create_flags(
            user_ids=[user.id],
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_id=entity_id,
        )
        if flags:
            affected_entity_ids.append(entity_id)

    logger.info(
        f"User {user.id} added {len(affected_entity_ids)} '{payload.flag_type}' flags "
        f"to {payload.entity_type} entities: {affected_entity_ids}"
    )

    return FlagModifyOut(
        flag_type=payload.flag_type,
        entity_type=payload.entity_type,
        entity_ids=affected_entity_ids,
    )


@router.delete(
    "/",
    response=FlagModifyOut,
    auth=JWTAuth(),
    summary="Remove flags from entities",
    description="Remove a flag from multiple entities for the authenticated user.",
)
def remove_flags(request, payload: FlagRequestIn):
    """
    Remove a flag from multiple entities.

    Deletes flag entries for the specified entities. If a flag doesn't exist
    for an entity, it's ignored (idempotent operation).
    """
    user = request.auth

    # Validate inputs
    validate_flag_type(payload.flag_type)
    validate_entity_type(payload.entity_type)

    if not payload.entity_ids:
        return FlagModifyOut(
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_ids=[],
        )

    # Authorize access to entities
    accessible_ids = authorize_entity_access(
        user, payload.entity_type, payload.entity_ids
    )

    if not accessible_ids:
        return FlagModifyOut(
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_ids=[],
        )

    # Get IDs that actually have flags before removing (to return accurate entity_ids)
    existing_flagged_ids = list(
        UserFlag.objects.get_flagged_entity_ids(
            user_id=user.id,
            flag_type=payload.flag_type,
            entity_type=payload.entity_type,
            entity_ids=accessible_ids,
        )
    )

    # Remove flags
    UserFlag.objects.remove_flags(
        user_id=user.id,
        flag_type=payload.flag_type,
        entity_type=payload.entity_type,
        entity_ids=accessible_ids,
    )

    logger.info(
        f"User {user.id} removed {len(existing_flagged_ids)} '{payload.flag_type}' flags "
        f"from {payload.entity_type} entities: {existing_flagged_ids}"
    )

    return FlagModifyOut(
        flag_type=payload.flag_type,
        entity_type=payload.entity_type,
        entity_ids=existing_flagged_ids,
    )
