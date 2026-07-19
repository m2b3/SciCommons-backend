import base64
import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import unquote, urlsplit, urlunsplit

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from ninja import Field, Query, Router, Schema
from ninja.responses import codes_4xx, codes_5xx
from rest_framework_simplejwt.tokens import RefreshToken

from articles.cache import invalidate_articles_cache
from articles.models import Article, ArticlePDF, Discussion, Review
from communities.models import Community, CommunityArticle
from myapp.schemas import Message
from users.auth import JWTAuth, OptionalJWTAuth
from users.models import ExtensionAuthCode, User

router = Router(tags=["Integrations"])
logger = logging.getLogger(__name__)


class PaperImportIn(Schema):
    title: str
    abstract: str = ""
    authors: List[Any] = Field(default_factory=list)
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None
    canonical_url: Optional[str] = None
    url: Optional[str] = None
    article_link: Optional[str] = None
    pdf_link: Optional[str] = None
    community_name: Optional[str] = None
    community_id: Optional[int] = None
    submission_type: Literal["Public", "Private"] = "Public"
    idempotency_key: Optional[str] = None


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


class ExtensionAuthorizeIn(Schema):
    client_id: str
    redirect_uri: str
    state: str
    code_challenge: str
    code_challenge_method: Literal["S256", "plain"] = "S256"


class ExtensionAuthorizeOut(Schema):
    code: str
    state: str
    redirect_uri: str
    expires_in: int


class ExtensionExchangeIn(Schema):
    client_id: str
    code: str
    code_verifier: str
    redirect_uri: Optional[str] = None


class ExtensionTokenOut(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]


def _normalize_doi(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized.strip() or None


def _normalize_pmid(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value.strip() if ch.isdigit())
    return digits or None


def _normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized.startswith("arxiv:"):
        normalized = normalized[len("arxiv:") :]
    if "arxiv.org/abs/" in normalized:
        normalized = normalized.split("arxiv.org/abs/", 1)[1]
    if "arxiv.org/pdf/" in normalized:
        normalized = normalized.split("arxiv.org/pdf/", 1)[1]
    normalized = normalized.removesuffix(".pdf")
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    if "#" in normalized:
        normalized = normalized.split("#", 1)[0]
    # arXiv versions point to the same paper for import/dedup purposes.
    parts = normalized.rsplit("v", 1)
    if len(parts) == 2 and parts[1].isdigit():
        normalized = parts[0]
    return normalized.strip("/") or None


def _normalize_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = urlsplit(raw)
        if not parsed.scheme or not parsed.netloc:
            return raw
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
    except Exception:
        return raw


def _article_url(article: Article) -> str:
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    return f"{frontend_url}/article/{article.slug}" if frontend_url else f"/article/{article.slug}"


def _normalize_authors(authors: List[Any]) -> List[Dict[str, str]]:
    normalized = []
    for author in authors or []:
        if isinstance(author, str):
            name = author.strip()
        elif isinstance(author, dict):
            name = str(
                author.get("label")
                or author.get("value")
                or author.get("name")
                or author.get("fullName")
                or ""
            ).strip()
        else:
            name = str(author).strip()

        if name:
            normalized.append({"label": name, "value": name})
    return normalized


def _find_article(
    doi: Optional[str],
    pmid: Optional[str],
    arxiv_id: Optional[str],
    url: Optional[str],
) -> Optional[Article]:
    query = Q()
    if doi:
        query |= Q(doi=doi)
    if pmid:
        query |= Q(pmid=pmid)
    if arxiv_id:
        query |= Q(arxiv_id=arxiv_id)
    if url:
        query |= Q(article_link=url) | Q(canonical_url=url)

    if not query:
        return None

    return Article.objects.filter(query).select_related("submitter").order_by("id").first()


def _current_user(request) -> Optional[User]:
    return request.auth if request.auth and not isinstance(request.auth, bool) else None


def _can_view_article(article: Article, user: Optional[User]) -> bool:
    if article.submission_type != "Private":
        return True
    return bool(user and article.submitter_id == user.id)


def _accessible_community_filter(user: Optional[User]) -> Q:
    community_filter = Q(community__isnull=True) | Q(community__type=Community.PUBLIC)
    if user:
        community_filter |= (
            Q(community__members=user)
            | Q(community__admins=user)
            | Q(community__moderators=user)
            | Q(community__reviewers=user)
        )
    return community_filter


def _resolve_community(payload: PaperImportIn, user: User):
    if not payload.community_id and not payload.community_name:
        return None, None

    try:
        if payload.community_id:
            community = Community.objects.get(id=payload.community_id)
        else:
            community = Community.objects.get(name=unquote(payload.community_name or ""))
    except Community.DoesNotExist:
        return None, (404, {"message": "Community not found."})

    has_private_access = (
        community.is_member(user)
        or community.is_admin(user)
        or community.moderators.filter(id=user.id).exists()
        or community.reviewers.filter(id=user.id).exists()
    )
    if community.type != Community.PUBLIC and not has_private_access:
        return None, (403, {"message": "You must be a member of this community to submit articles."})

    return community, None


def _ensure_community_article(article: Article, community: Optional[Community], user: User):
    if not community:
        return None

    existing = CommunityArticle.objects.filter(article=article, community=community).first()
    if existing:
        return existing

    status = (
        CommunityArticle.PUBLISHED
        if community.type in {Community.PRIVATE, Community.HIDDEN} or community.admins.filter(id=user.id).exists()
        else CommunityArticle.SUBMITTED
    )
    return CommunityArticle.objects.create(article=article, community=community, status=status)


def _attach_pdf_link(article: Article, pdf_link: Optional[str]):
    normalized_pdf_link = _normalize_url(pdf_link)
    if not normalized_pdf_link:
        return
    ArticlePDF.objects.get_or_create(article=article, external_url=normalized_pdf_link, defaults={"pdf_file_url": None})


def _hash_code(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str, method: str) -> str:
    if method == "plain":
        return verifier
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _is_allowed_redirect_uri(redirect_uri: str) -> bool:
    try:
        parsed = urlsplit(redirect_uri)
    except Exception:
        return False

    if parsed.scheme == "chrome-extension" and parsed.netloc:
        return True
    if parsed.scheme == "https" and parsed.netloc.endswith(".chromiumapp.org"):
        return True
    if settings.DEBUG and parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}:
        return True

    allowed_prefixes = getattr(settings, "EXTENSION_ALLOWED_REDIRECT_URI_PREFIXES", [])
    return any(redirect_uri.startswith(prefix) for prefix in allowed_prefixes)


@router.get(
    "/papers/lookup",
    response={200: PaperLookupOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def lookup_paper(
    request,
    doi: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    arxiv_id: Optional[str] = Query(None),
    url: Optional[str] = Query(None),
):
    normalized_doi = _normalize_doi(doi)
    normalized_pmid = _normalize_pmid(pmid)
    normalized_arxiv_id = _normalize_arxiv_id(arxiv_id)
    normalized_url = _normalize_url(url)

    article = _find_article(normalized_doi, normalized_pmid, normalized_arxiv_id, normalized_url)
    user = _current_user(request)
    if not article or not _can_view_article(article, user):
        return 200, PaperLookupOut(found=False)

    accessible_filter = _accessible_community_filter(user)
    total_discussions = Discussion.objects.filter(article=article).filter(accessible_filter).distinct().count()
    total_reviews = Review.objects.filter(article=article).filter(accessible_filter).distinct().count()

    return 200, PaperLookupOut(
        found=True,
        article_id=article.id,
        slug=article.slug,
        title=article.title,
        article_url=_article_url(article),
        doi=article.doi,
        pmid=article.pmid,
        arxiv_id=article.arxiv_id,
        total_discussions=total_discussions,
        total_reviews=total_reviews,
        can_post_discussion=bool(user),
    )


@router.post(
    "/papers/import",
    response={200: PaperImportOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def import_paper(request, payload: PaperImportIn):
    user = request.auth
    doi = _normalize_doi(payload.doi)
    pmid = _normalize_pmid(payload.pmid)
    arxiv_id = _normalize_arxiv_id(payload.arxiv_id)
    source_url = _normalize_url(payload.article_link or payload.url or payload.canonical_url)
    canonical_url = _normalize_url(payload.canonical_url or source_url)

    if not payload.title.strip():
        return 400, {"message": "Title is required."}

    community, error = _resolve_community(payload, user)
    if error:
        return error

    with transaction.atomic():
        article = _find_article(doi, pmid, arxiv_id, source_url or canonical_url)
        found_existing = article is not None

        if not article:
            article = Article.objects.create(
                title=payload.title.strip(),
                abstract=payload.abstract.strip(),
                authors=_normalize_authors(payload.authors),
                doi=doi,
                pmid=pmid,
                arxiv_id=arxiv_id,
                canonical_url=canonical_url,
                article_link=source_url,
                submission_type=payload.submission_type,
                submitter=user,
            )
            invalidate_articles_cache()
        else:
            fields_to_update = []
            for field, value in {
                "doi": doi,
                "pmid": pmid,
                "arxiv_id": arxiv_id,
                "canonical_url": canonical_url,
            }.items():
                if value and not getattr(article, field):
                    setattr(article, field, value)
                    fields_to_update.append(field)
            if fields_to_update:
                article.save(update_fields=fields_to_update + ["updated_at"])

        _attach_pdf_link(article, payload.pdf_link)
        community_article = _ensure_community_article(article, community, user)

    return 200, PaperImportOut(
        found_existing=found_existing,
        article_id=article.id,
        slug=article.slug,
        title=article.title,
        article_url=_article_url(article),
        doi=article.doi,
        pmid=article.pmid,
        arxiv_id=article.arxiv_id,
        community_article_id=community_article.id if community_article else None,
        community_submission_status=community_article.status if community_article else None,
    )


@router.post(
    "/extension/authorize",
    response={200: ExtensionAuthorizeOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def authorize_extension(request, payload: ExtensionAuthorizeIn):
    if not _is_allowed_redirect_uri(payload.redirect_uri):
        return 400, {"message": "Invalid extension redirect URI."}

    code = secrets.token_urlsafe(32)
    ttl_seconds = getattr(settings, "EXTENSION_AUTH_CODE_TTL_SECONDS", 300)
    ExtensionAuthCode.objects.create(
        user=request.auth,
        client_id=payload.client_id,
        code_hash=_hash_code(code),
        code_challenge=payload.code_challenge,
        code_challenge_method=payload.code_challenge_method,
        redirect_uri=payload.redirect_uri,
        state=payload.state,
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )

    return 200, ExtensionAuthorizeOut(
        code=code,
        state=payload.state,
        redirect_uri=payload.redirect_uri,
        expires_in=ttl_seconds,
    )


@router.post(
    "/extension/exchange",
    response={200: ExtensionTokenOut, codes_4xx: Message, codes_5xx: Message},
)
def exchange_extension_code(request, payload: ExtensionExchangeIn):
    code_hash = _hash_code(payload.code)
    with transaction.atomic():
        auth_code = (
            ExtensionAuthCode.objects.select_for_update().select_related("user").filter(code_hash=code_hash).first()
        )
        if not auth_code:
            return 400, {"message": "Invalid extension authorization code."}
        if auth_code.is_used:
            return 400, {"message": "Extension authorization code has already been used."}
        if auth_code.is_expired:
            return 400, {"message": "Extension authorization code has expired."}
        if auth_code.client_id != payload.client_id:
            return 400, {"message": "Extension client mismatch."}
        if payload.redirect_uri and payload.redirect_uri != auth_code.redirect_uri:
            return 400, {"message": "Extension redirect URI mismatch."}

        expected_challenge = _pkce_challenge(payload.code_verifier, auth_code.code_challenge_method)
        if not constant_time_compare(expected_challenge, auth_code.code_challenge):
            return 400, {"message": "Invalid extension PKCE verifier."}

        auth_code.mark_used()
        user = auth_code.user

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    access_lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME")
    expires_in = int(access_lifetime.total_seconds()) if access_lifetime else 86400

    return 200, ExtensionTokenOut(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    )
