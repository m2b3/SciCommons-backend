from typing import List, Literal, Optional

from ninja import Schema


class Message(Schema):
    message: str


class IntegrationUserOut(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class PaperAuthorIn(Schema):
    label: Optional[str] = None
    value: Optional[str] = None
    name: Optional[str] = None


class PaperImportIn(Schema):
    title: str
    abstract: Optional[str] = ""
    authors: List[PaperAuthorIn | str] = []
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None
    canonical_url: Optional[str] = None
    url: Optional[str] = None
    article_link: Optional[str] = None
    pdf_link: Optional[str] = None
    community_id: Optional[int] = None
    community_name: Optional[str] = None
    submission_type: Literal["Public", "Private"] = "Public"
    idempotency_key: Optional[str] = None


class PaperLookupOut(Schema):
    found: bool
    article_id: Optional[int] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    article_url: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None
    total_discussions: int = 0
    total_reviews: int = 0
    can_post_discussion: bool = False


class PaperImportOut(Schema):
    found_existing: bool
    article_id: int
    slug: str
    title: str
    article_url: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None
    community_article_id: Optional[int] = None
    community_submission_status: Optional[str] = None


class IntegrationAuthorizeIn(Schema):
    client_id: str
    redirect_uri: str
    state: Optional[str] = None
    code_challenge: str
    code_challenge_method: Literal["S256"] = "S256"


class IntegrationAuthorizeOut(Schema):
    code: str
    state: Optional[str] = None
    redirect_uri: str
    expires_in: int


class IntegrationExchangeIn(Schema):
    client_id: str
    code: str
    code_verifier: str
    redirect_uri: str


class IntegrationTokenOut(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: IntegrationUserOut


class DeviceStartIn(Schema):
    client_id: str


class DeviceStartOut(Schema):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceApproveIn(Schema):
    user_code: str
    client_id: Optional[str] = None


class DeviceTokenIn(Schema):
    client_id: str
    device_code: str
