from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from ninja import Schema
from pydantic import ConfigDict, Field


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


class OpenFeedSchema(Schema):
    """Feed-server payloads are forward-compatible and may include extension fields."""

    model_config = ConfigDict(extra="allow")


class FeedArticleOut(OpenFeedSchema):
    id: Optional[str] = None
    paper_key: Optional[str] = None
    source: str = ""
    title: str = ""
    authors: Union[str, List[str]] = ""
    abstract: str = ""
    tags: List[str] = Field(default_factory=list)
    url: str = ""
    score: Optional[float] = None
    rank: Optional[int] = None
    categories: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    available_date: Optional[str] = None
    published_date: Optional[str] = None
    fetched_at: Optional[str] = None
    pdf_url: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    matched_interest: Optional[str] = None
    feedback: Optional[Literal["like", "dislike", ""]] = None


class FeedDescriptionOut(OpenFeedSchema):
    id: str
    slug: str
    display_name: str
    privacy: Literal["private", "unlisted", "public"]
    configuration_version: int
    generation_status: Literal["pending", "running", "ready", "failed"]
    interests: List[str] = Field(default_factory=list)
    authors: List[str] = Field(default_factory=list)
    user_id: Optional[str] = None
    feed_slug: Optional[str] = None
    follower_count: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    can_edit: Optional[bool] = None
    links: Optional[Dict[str, Any]] = None


class FeedPageResponseOut(OpenFeedSchema):
    feed: FeedDescriptionOut
    generation: Optional[int] = None
    status: str
    counts: Dict[str, int] = Field(default_factory=dict)
    items: List[FeedArticleOut] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    has_more: bool
    total: int
