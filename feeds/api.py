import logging
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from ninja import Query, Router
from ninja.errors import HttpError, HttpRequest
from ninja.responses import codes_4xx, codes_5xx

from feeds.models import FeedPreference
from feeds.schemas import FeedPreferenceIn, FeedPreferenceOut
from myapp.schemas import Message
from users.auth import JWTAuth

router = Router(tags=["Feeds"])

logger = logging.getLogger(__name__)

# Caps keep a pasted spreadsheet from writing an unbounded row.
MAX_ENTRIES_PER_FIELD = 100
MAX_ENTRY_LENGTH = 500
STATIC_MAIN_FEED_PATH = Path(__file__).resolve().parent / "fixtures" / "u1-main-feed.json"
STATIC_CURSOR_PREFIX = "static:"


@lru_cache(maxsize=1)
def load_static_main_feed() -> dict:
    with STATIC_MAIN_FEED_PATH.open(encoding="utf-8") as feed_file:
        return json.load(feed_file)


def decode_static_cursor(cursor: Optional[str]) -> int:
    if not cursor:
        return 0

    if not cursor.startswith(STATIC_CURSOR_PREFIX):
        raise HttpError(400, "Invalid feed cursor.")

    try:
        offset = int(cursor.removeprefix(STATIC_CURSOR_PREFIX))
    except ValueError as exc:
        raise HttpError(400, "Invalid feed cursor.") from exc

    if offset < 0:
        raise HttpError(400, "Invalid feed cursor.")

    return offset


def build_static_main_feed_page(source: Literal["all", "arxiv", "pubmed"], limit: int, cursor: Optional[str]) -> dict:
    page = deepcopy(load_static_main_feed())
    all_items = page.get("items", [])
    selected_items = all_items if source == "all" else [item for item in all_items if item.get("source") == source]

    offset = decode_static_cursor(cursor)
    next_offset = offset + limit
    page_items = selected_items[offset:next_offset]

    page["items"] = page_items
    page["total"] = len(selected_items)
    page["has_more"] = next_offset < len(selected_items)
    page["next_cursor"] = f"{STATIC_CURSOR_PREFIX}{next_offset}" if page["has_more"] else None

    return page


def clean_entries(values: List[str]) -> List[str]:
    """
    Normalise one preference list: trim, drop blanks, drop case-insensitive
    duplicates (keeping the first spelling the user typed), and cap the size.
    """
    cleaned: List[str] = []
    seen = set()

    for raw_value in values:
        if not isinstance(raw_value, str):
            continue

        value = raw_value.strip()
        if not value:
            continue

        value = value[:MAX_ENTRY_LENGTH]

        key = value.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

        if len(cleaned) >= MAX_ENTRIES_PER_FIELD:
            break

    return cleaned


def serialize(preference: FeedPreference) -> dict:
    return {
        "topics": preference.topics or [],
        "authors": preference.authors or [],
        "keywords": preference.keywords or [],
        "similar_to": preference.similar_to or [],
        "has_saved_preferences": True,
        "updated_at": preference.updated_at,
    }


@router.get(
    "/main/items",
    response={200: Dict[str, Any], codes_4xx: Message, codes_5xx: Message},
)
def get_main_feed_items(
    request: HttpRequest,
    source: Literal["all", "arxiv", "pubmed"] = Query("all"),
    limit: int = Query(40, ge=1, le=100),
    cursor: Optional[str] = Query(None),
):
    """
    Return the static feed-server handoff payload for the SciCommons front page.

    This mirrors the feed service's page contract while the user-specific feed
    database integration is being set up.
    """
    return 200, build_static_main_feed_page(source, limit, cursor)


@router.get(
    "/preferences",
    response={200: FeedPreferenceOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_feed_preferences(request: HttpRequest):
    """
    Get the logged-in user's feed preferences.
    Returns empty lists when the user has not saved any preferences yet.
    """
    user = request.auth

    preference = FeedPreference.objects.filter(user_id=user.id).first()
    if preference is None:
        return 200, {"has_saved_preferences": False}

    return 200, serialize(preference)


@router.put(
    "/preferences",
    response={200: FeedPreferenceOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def update_feed_preferences(request: HttpRequest, payload: FeedPreferenceIn):
    """
    Create or update the logged-in user's feed preferences row.

    The payload always carries the full set of preferences, so editing a single
    field on the form and saving keeps the stored row in sync with the form.
    """
    user = request.auth

    preference, _ = FeedPreference.objects.update_or_create(
        user_id=user.id,
        defaults={
            "username": user.username,
            "topics": clean_entries(payload.topics),
            "authors": clean_entries(payload.authors),
            "keywords": clean_entries(payload.keywords),
            "similar_to": clean_entries(payload.similar_to),
        },
    )

    return 200, serialize(preference)
