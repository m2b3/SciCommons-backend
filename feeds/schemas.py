from datetime import datetime
from typing import List, Optional

from ninja import Schema


class FeedPreferenceIn(Schema):
    """Payload sent by the feed-preferences form (and by template imports)."""

    topics: List[str] = []
    authors: List[str] = []
    keywords: List[str] = []
    similar_to: List[str] = []


class FeedPreferenceOut(Schema):
    """Current feed preferences for the logged-in user."""

    topics: List[str] = []
    authors: List[str] = []
    keywords: List[str] = []
    similar_to: List[str] = []
    # False until the user saves for the first time; the lists above are empty in that case.
    has_saved_preferences: bool = False
    updated_at: Optional[datetime] = None
