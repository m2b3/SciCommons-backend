import logging
from typing import List

from ninja import Router
from ninja.errors import HttpRequest
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
