import base64
import hashlib
import secrets
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx
from rest_framework_simplejwt.tokens import RefreshToken

from articles.models import Article, ArticlePDF
from communities.models import Community, CommunityArticle
from integrations.models import IntegrationAuthCode, IntegrationDeviceAuth, hash_secret
from integrations.schemas import (
    DeviceApproveIn,
    DeviceStartIn,
    DeviceStartOut,
    DeviceTokenIn,
    IntegrationAuthorizeIn,
    IntegrationAuthorizeOut,
    IntegrationExchangeIn,
    IntegrationTokenOut,
    Message,
    PaperImportIn,
    PaperImportOut,
    PaperLookupOut,
)
from users.auth import JWTAuth, OptionalJWTAuth

router = Router(tags=["Integrations"])

DEFAULT_AUTH_CODE_TTL_SECONDS = 300
DEFAULT_DEVICE_CODE_TTL_SECONDS = 900
DEFAULT_DEVICE_POLL_INTERVAL_SECONDS = 5


def _clean_text(value: Optional[str]) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_doi(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    cleaned = cleaned.replace("https://doi.org/", "").replace("http://doi.org/", "")
    cleaned = cleaned.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    if cleaned.lower().startswith("doi:"):
        cleaned = cleaned[4:].strip()
    return cleaned.rstrip(".,;)]").lower() or None


def _normalize_pmid(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    return cleaned.replace("PMID:", "").replace("pmid:", "").strip() or None


def _normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    cleaned = cleaned.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
    cleaned = cleaned.replace("https://arxiv.org/pdf/", "").replace("http://arxiv.org/pdf/", "")
    cleaned = cleaned.replace(".pdf", "")
    if cleaned.lower().startswith("arxiv:"):
        cleaned = cleaned[6:]
    return cleaned.rstrip(".,;)]").lower() or None


def _normalize_url(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return cleaned
    normalized = parsed._replace(fragment="")
    path = normalized.path.rstrip("/") or normalized.path
    normalized = normalized._replace(path=path)
    return urlunparse(normalized)


def _article_url(article: Article) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/article/{article.slug}"


def _auth_user(request):
    user = getattr(request, "auth", None)
    return None if user is True else user


def _user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def _token_payload(user) -> dict:
    refresh = RefreshToken.for_user(user)
    access_lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", timedelta(days=1))
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "token_type": "Bearer",
        "expires_in": int(access_lifetime.total_seconds()),
        "user": _user_payload(user),
    }


def _authors_to_tags(authors) -> list[dict[str, str]]:
    tags = []
    for author in authors or []:
        if isinstance(author, str):
            name = _clean_text(author)
        else:
            name = _clean_text(
                getattr(author, "label", None)
                or getattr(author, "value", None)
                or getattr(author, "name", None)
            )
        if name:
            tags.append({"label": name, "value": name})
    return tags


def _matching_articles(doi=None, pmid=None, arxiv_id=None, canonical_url=None, url=None):
    query = Q()
    has_filter = False
    for field, value in (
        ("doi__iexact", _normalize_doi(doi)),
        ("pmid__iexact", _normalize_pmid(pmid)),
        ("arxiv_id__iexact", _normalize_arxiv_id(arxiv_id)),
        ("canonical_url", _normalize_url(canonical_url)),
        ("article_link", _normalize_url(url)),
    ):
        if value:
            query |= Q(**{field: value})
            has_filter = True
    if not has_filter:
        return Article.objects.none()
    return Article.objects.filter(query).order_by("id")


def _visible_articles_for_user(queryset, user):
    if user is None:
        return queryset.filter(submission_type="Public")
    return queryset.filter(Q(submission_type="Public") | Q(submitter=user))


def _serialize_lookup(article: Optional[Article], user=None) -> dict:
    if article is None:
        return {"found": False, "can_post_discussion": user is not None}
    return {
        "found": True,
        "article_id": article.id,
        "slug": article.slug,
        "title": article.title,
        "article_url": _article_url(article),
        "doi": article.doi,
        "pmid": article.pmid,
        "arxiv_id": article.arxiv_id,
        "total_discussions": article.discussions.filter(deleted_at__isnull=True).count(),
        "total_reviews": article.reviews.filter(deleted_at__isnull=True).count(),
        "can_post_discussion": user is not None,
    }


def _serialize_import(article: Article, found_existing: bool, community_article=None) -> dict:
    return {
        "found_existing": found_existing,
        "article_id": article.id,
        "slug": article.slug,
        "title": article.title,
        "article_url": _article_url(article),
        "doi": article.doi,
        "pmid": article.pmid,
        "arxiv_id": article.arxiv_id,
        "community_article_id": community_article.id if community_article else None,
        "community_submission_status": community_article.status if community_article else None,
    }


def _resolve_community(payload: PaperImportIn):
    if payload.community_id:
        return Community.objects.filter(id=payload.community_id).first()
    if payload.community_name:
        community_name = _clean_text(payload.community_name)
        return Community.objects.filter(Q(name__iexact=community_name) | Q(slug=slugify(community_name))).first()
    return None


def _community_status(community: Community, user) -> str:
    if community.type in {Community.PRIVATE, Community.HIDDEN} or community.admins.filter(id=user.id).exists():
        return CommunityArticle.PUBLISHED
    return CommunityArticle.SUBMITTED


def _ensure_community_article(article: Article, community: Optional[Community], user):
    if community is None:
        return None
    community_article = CommunityArticle.objects.filter(article=article, community=community).first()
    if community_article:
        return community_article
    return CommunityArticle.objects.create(
        article=article,
        community=community,
        status=_community_status(community, user),
    )


def _is_allowed_redirect_uri(client_id: str, redirect_uri: str) -> bool:
    parsed = urlparse(redirect_uri)
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"} and settings.DEBUG:
        return True
    if client_id == "scicommons-clipper":
        if parsed.scheme == "chrome-extension":
            return True
        if parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".chromiumapp.org"):
            return True
    allowed_prefixes = getattr(settings, "INTEGRATION_ALLOWED_REDIRECT_URI_PREFIXES", [])
    return any(redirect_uri.startswith(prefix) for prefix in allowed_prefixes)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _auth_code_ttl_seconds() -> int:
    return int(getattr(settings, "INTEGRATION_AUTH_CODE_TTL_SECONDS", DEFAULT_AUTH_CODE_TTL_SECONDS))


@router.get(
    "/papers/lookup",
    response={200: PaperLookupOut, codes_4xx: Message, codes_5xx: Message},
    auth=OptionalJWTAuth,
)
def lookup_paper(
    request,
    doi: Optional[str] = None,
    pmid: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    url: Optional[str] = None,
):
    user = _auth_user(request)
    article = _visible_articles_for_user(
        _matching_articles(doi=doi, pmid=pmid, arxiv_id=arxiv_id, canonical_url=url, url=url),
        user,
    ).first()
    return _serialize_lookup(article, user)


@router.post(
    "/papers/import",
    response={200: PaperImportOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def import_paper(request, payload: PaperImportIn):
    title = _clean_text(payload.title)
    if not title:
        return 400, {"message": "Title is required."}

    user = request.auth
    doi = _normalize_doi(payload.doi)
    pmid = _normalize_pmid(payload.pmid)
    arxiv_id = _normalize_arxiv_id(payload.arxiv_id)
    canonical_url = _normalize_url(payload.canonical_url or payload.url or payload.article_link)
    article_link = _normalize_url(payload.article_link or payload.url)
    community = _resolve_community(payload)
    if (payload.community_id or payload.community_name) and community is None:
        return 404, {"message": "Community not found."}

    with transaction.atomic():
        article = (
            _visible_articles_for_user(
                _matching_articles(
                    doi=doi,
                    pmid=pmid,
                    arxiv_id=arxiv_id,
                    canonical_url=canonical_url,
                    url=article_link,
                ),
                user,
            )
            .select_for_update()
            .first()
        )
        found_existing = article is not None

        if article is None:
            article = Article.objects.create(
                title=title,
                abstract=payload.abstract or "",
                authors=_authors_to_tags(payload.authors),
                article_link=article_link,
                doi=doi,
                pmid=pmid,
                arxiv_id=arxiv_id,
                canonical_url=canonical_url,
                submission_type=payload.submission_type,
                submitter=user,
            )
        else:
            changed_fields = []
            for field, value in (
                ("doi", doi),
                ("pmid", pmid),
                ("arxiv_id", arxiv_id),
                ("canonical_url", canonical_url),
            ):
                if value and not getattr(article, field):
                    setattr(article, field, value)
                    changed_fields.append(field)
            if changed_fields:
                article.save(update_fields=changed_fields)

        if payload.pdf_link and not ArticlePDF.objects.filter(article=article, external_url=payload.pdf_link).exists():
            ArticlePDF.objects.create(article=article, external_url=payload.pdf_link)

        community_article = _ensure_community_article(article, community, user)

    return _serialize_import(article, found_existing, community_article)


@router.post(
    "/auth/authorize",
    response={200: IntegrationAuthorizeOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def authorize_integration(request, payload: IntegrationAuthorizeIn):
    if not _is_allowed_redirect_uri(payload.client_id, payload.redirect_uri):
        return 400, {"message": "Redirect URI is not allowed for this integration."}

    code = secrets.token_urlsafe(32)
    ttl_seconds = _auth_code_ttl_seconds()
    IntegrationAuthCode.objects.create(
        client_id=payload.client_id,
        user=request.auth,
        code_hash=hash_secret(code),
        code_challenge=payload.code_challenge,
        code_challenge_method=payload.code_challenge_method,
        redirect_uri=payload.redirect_uri,
        state=payload.state,
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )
    return {
        "code": code,
        "state": payload.state,
        "redirect_uri": payload.redirect_uri,
        "expires_in": ttl_seconds,
    }


@router.post(
    "/extension/authorize",
    response={200: IntegrationAuthorizeOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def authorize_extension(request, payload: IntegrationAuthorizeIn):
    return authorize_integration(request, payload)


@router.post(
    "/auth/exchange",
    response={200: IntegrationTokenOut, codes_4xx: Message, codes_5xx: Message},
)
def exchange_integration_code(request, payload: IntegrationExchangeIn):
    auth_code = IntegrationAuthCode.objects.select_related("user").filter(code_hash=hash_secret(payload.code)).first()
    if (
        auth_code is None
        or auth_code.client_id != payload.client_id
        or auth_code.redirect_uri != payload.redirect_uri
        or auth_code.is_used
        or auth_code.is_expired
    ):
        return 400, {"message": "Authorization code is invalid or expired."}
    if not secrets.compare_digest(_pkce_challenge(payload.code_verifier), auth_code.code_challenge):
        return 400, {"message": "Code verifier is invalid."}

    auth_code.mark_used()
    return _token_payload(auth_code.user)


@router.post(
    "/extension/exchange",
    response={200: IntegrationTokenOut, codes_4xx: Message, codes_5xx: Message},
)
def exchange_extension_code(request, payload: IntegrationExchangeIn):
    return exchange_integration_code(request, payload)


@router.post(
    "/auth/device/start",
    response={200: DeviceStartOut, codes_4xx: Message, codes_5xx: Message},
)
def start_device_auth(request, payload: DeviceStartIn):
    device_code = secrets.token_urlsafe(40)
    user_code = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
    expires_in = int(getattr(settings, "INTEGRATION_DEVICE_CODE_TTL_SECONDS", DEFAULT_DEVICE_CODE_TTL_SECONDS))
    interval = int(getattr(settings, "INTEGRATION_DEVICE_POLL_INTERVAL_SECONDS", DEFAULT_DEVICE_POLL_INTERVAL_SECONDS))

    IntegrationDeviceAuth.objects.create(
        client_id=payload.client_id,
        device_code_hash=hash_secret(device_code),
        user_code_hash=hash_secret(user_code),
        expires_at=timezone.now() + timedelta(seconds=expires_in),
        interval_seconds=interval,
    )

    verification_uri = f"{settings.FRONTEND_URL.rstrip('/')}/auth/device"
    verification_uri_complete = f"{verification_uri}?{urlencode({'code': user_code})}"
    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": verification_uri_complete,
        "expires_in": expires_in,
        "interval": interval,
    }


@router.post(
    "/auth/device/approve",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def approve_device_auth(request, payload: DeviceApproveIn):
    user_code = _clean_text(payload.user_code).upper()
    query = IntegrationDeviceAuth.objects.filter(user_code_hash=hash_secret(user_code))
    if payload.client_id:
        query = query.filter(client_id=payload.client_id)
    device_auth = query.first()
    if device_auth is None or device_auth.is_expired:
        return 400, {"message": "Device authorization code is invalid or expired."}
    if device_auth.status != IntegrationDeviceAuth.PENDING:
        return 400, {"message": "Device authorization code has already been used."}

    device_auth.approve(request.auth)
    return {"message": "SciCommons access approved."}


@router.post(
    "/auth/device/token",
    response={200: IntegrationTokenOut, 202: Message, codes_4xx: Message, codes_5xx: Message},
)
def exchange_device_token(request, payload: DeviceTokenIn):
    device_auth = (
        IntegrationDeviceAuth.objects.select_related("user")
        .filter(client_id=payload.client_id, device_code_hash=hash_secret(payload.device_code))
        .first()
    )
    if device_auth is None or device_auth.is_expired:
        return 400, {"message": "Device code is invalid or expired."}
    if device_auth.status == IntegrationDeviceAuth.PENDING:
        return 202, {"message": "Authorization pending."}
    if device_auth.status == IntegrationDeviceAuth.CONSUMED or device_auth.user is None:
        return 400, {"message": "Device code has already been used."}

    token_payload = _token_payload(device_auth.user)
    device_auth.consume()
    return token_payload
