import base64
import hashlib
import logging
import secrets
from datetime import timedelta
from typing import List, Optional
from urllib.parse import quote, urlencode, urlparse, urlunparse

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from django_ratelimit.decorators import ratelimit
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
logger = logging.getLogger(__name__)

#: How long a successful import is remembered per (user, communities, idempotency_key).
IMPORT_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

#: Arbitrary namespace for pg_advisory_xact_lock so import locks cannot collide with other
#: advisory-lock users in the same database.
IMPORT_LOCK_NAMESPACE = 0x5C10

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


def _community_article_url(article: Article, community: Community) -> str:
    community_path = quote(community.name, safe="")
    return f"{settings.FRONTEND_URL.rstrip('/')}/community/{community_path}/articles/{article.slug}"


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


def _visible_articles_for_user(queryset, user, community_ids: Optional[List[int]] = None):
    if user is None:
        return queryset.filter(submission_type="Public")

    visibility_filter = Q(submission_type="Public") | Q(submitter=user)
    if community_ids:
        visible_community_articles = CommunityArticle.objects.filter(
            community_id__in=community_ids,
        ).values("article_id")
        visibility_filter |= Q(id__in=visible_community_articles)
    return queryset.filter(visibility_filter)


def _accessible_community_filter(user) -> Q:
    """Rows with no community, in a public community, or in one the user belongs to."""
    community_filter = Q(community__isnull=True) | Q(community__type=Community.PUBLIC)
    if user is not None:
        community_filter |= (
            Q(community__members=user)
            | Q(community__admins=user)
            | Q(community__moderators=user)
            | Q(community__reviewers=user)
        )
    return community_filter


def _identifier_matches(
    doi=None,
    pmid=None,
    arxiv_id=None,
    canonical_url=None,
    url=None,
    user=None,
    community_ids: Optional[List[int]] = None,
) -> dict:
    """Resolve each identifier independently so disagreement is detectable.

    `_matching_articles` ORs every identifier and the caller takes `.first()`, so a DOI
    belonging to one paper and a PMID belonging to another silently selected whichever had the
    lower id -- and then backfilled identifiers onto it and attached it to a community.
    """
    matches = {}
    for name, field, value in (
        ("doi", "doi__iexact", _normalize_doi(doi)),
        ("pmid", "pmid__iexact", _normalize_pmid(pmid)),
        ("arxiv_id", "arxiv_id__iexact", _normalize_arxiv_id(arxiv_id)),
        ("canonical_url", "canonical_url", _normalize_url(canonical_url)),
        ("url", "article_link", _normalize_url(url)),
    ):
        if not value:
            continue
        found = _visible_articles_for_user(
            Article.objects.filter(**{field: value}),
            user,
            community_ids=community_ids,
        ).order_by("id").first()
        if found:
            matches[name] = found
    return matches


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
        # Counts are filtered by community visibility. Previously they counted every
        # discussion/review on the article, so anyone who could see a public paper learned how
        # much activity existed inside private and hidden communities they had no access to.
        "total_discussions": article.discussions.filter(deleted_at__isnull=True)
        .filter(_accessible_community_filter(user))
        .distinct()
        .count(),
        "total_reviews": article.reviews.filter(deleted_at__isnull=True)
        .filter(_accessible_community_filter(user))
        .distinct()
        .count(),
        "can_post_discussion": user is not None,
    }


def _serialize_import(article: Article, found_existing: bool, community_results: Optional[List[dict]] = None) -> dict:
    community_results = community_results or []
    # First successful attachment fills the legacy single-community fields.
    first_attached = next((result for result in community_results if result.get("attached")), None)
    return {
        "found_existing": found_existing,
        "article_id": article.id,
        "slug": article.slug,
        "title": article.title,
        "article_url": first_attached.get("article_url") if first_attached else _article_url(article),
        "doi": article.doi,
        "pmid": article.pmid,
        "arxiv_id": article.arxiv_id,
        "community_article_id": first_attached.get("community_article_id") if first_attached else None,
        "community_submission_status": first_attached.get("status") if first_attached else None,
        "communities": community_results,
    }


def _find_community(name_or_slug: str) -> Optional[Community]:
    cleaned = _clean_text(name_or_slug)
    if not cleaned:
        return None
    return Community.objects.filter(Q(name__iexact=cleaned) | Q(slug=slugify(cleaned))).first()


def _may_submit_to_community(community: Community, user) -> bool:
    """Mirrors the membership gate in communities/articles_api.py submit_article.

    Previously absent: `_resolve_community` took no user at all, so ANY authenticated user
    could attach a paper to ANY community -- and because `_community_status` publishes
    straight away for private/hidden communities, that paper was immediately visible to a
    community the caller had no part in. Public communities stay open to any member of the
    site, matching the existing submit_article policy.
    """
    if community.type == Community.PUBLIC:
        return True
    return (
        community.is_member(user)
        or community.is_admin(user)
        or community.moderators.filter(id=user.id).exists()
        or community.reviewers.filter(id=user.id).exists()
    )


def _requested_community_names(payload: PaperImportIn) -> List[str]:
    """Ordered, de-duplicated community names from any of the accepted request shapes.

    `community_names` is the current field; `community_name` (singular) and `community_id`
    are still honoured so older clients keep working.
    """
    names: List[str] = []

    def add(value: Optional[str]):
        cleaned = _clean_text(value or "")
        if cleaned and not any(cleaned.lower() == existing.lower() for existing in names):
            names.append(cleaned)

    for raw in payload.community_names or []:
        # Tolerate a client sending one comma-joined string in the list.
        for part in str(raw).split(","):
            add(part)
    for part in (payload.community_name or "").split(","):
        add(part)

    if payload.community_id:
        community = Community.objects.filter(id=payload.community_id).first()
        if community:
            add(community.name)
        else:
            # Report explicit bad ids through the same per-community result shape.
            names.append(f"#{payload.community_id}")

    return names


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


def _attach_to_communities(article: Article, names: List[str], user) -> List[dict]:
    """Attach the article to each named community the user is allowed to submit to.

    Returns one result per requested name. Unknown names and permission failures are reported
    per name rather than failing the whole import, so typing three names and getting two wrong
    still files the paper where it can.
    """
    results = []
    for name in names:
        community = _find_community(name) if not name.startswith("#") else None
        if community is None:
            results.append({"name": name, "attached": False, "error": "Community not found."})
            continue

        if not _may_submit_to_community(community, user):
            results.append(
                {
                    "name": community.name,
                    "attached": False,
                    "error": "You must be a member of this community to submit articles.",
                }
            )
            continue

        community_article = _ensure_community_article(article, community, user)
        results.append(
            {
                "name": community.name,
                "attached": True,
                "community_article_id": community_article.id,
                "status": community_article.status,
                "article_url": _community_article_url(article, community),
            }
        )
    return results


def _allowed_requested_community_ids(names: List[str], user) -> List[int]:
    """Community ids that may contribute visible existing articles for this import.

    This keeps the private-article leak closed while still allowing a member to save a paper
    into a community without duplicating an article already filed there by another member.
    """
    community_ids = []
    for name in names:
        if name.startswith("#"):
            continue
        community = _find_community(name)
        if community and _may_submit_to_community(community, user):
            community_ids.append(community.id)
    return community_ids


#: Crockford-style base32 minus vowels and easily-confused glyphs, so codes are safe to read
#: aloud and retype. 28 symbols over 10 characters is ~48 bits, versus the previous 8 hex
#: characters (32 bits) which was brute-forceable inside the 15-minute window.
USER_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTVWXZ"
USER_CODE_LENGTH = 10


def _generate_user_code() -> str:
    body = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))
    return f"{body[:5]}-{body[5:]}"


def _normalize_user_code(value: str) -> str:
    """Uppercase and strip formatting so "abcde-fghjk" and "ABCDEFGHJK" hash alike."""
    cleaned = _clean_text(value).upper().replace("-", "").replace(" ", "")
    return f"{cleaned[:5]}-{cleaned[5:]}" if len(cleaned) == USER_CODE_LENGTH else cleaned


def _is_allowed_client_id(client_id: str) -> bool:
    """`client_id` is caller-supplied free text, so it must be checked against a registry.

    Previously the only validation anywhere was a single hardcoded `== "scicommons-clipper"`
    inside the redirect check, which meant any other value was accepted unconditionally.
    """
    allowed = getattr(settings, "INTEGRATION_ALLOWED_CLIENT_IDS", [])
    return client_id in allowed if allowed else False


def _is_allowed_redirect_uri(client_id: str, redirect_uri: str) -> bool:
    """Exact-match a configured redirect URI.

    This used to accept ANY `chrome-extension://` URI and ANY `*.chromiumapp.org` host for the
    clipper client -- i.e. every Chrome extension in existence, since both are derived straight
    from the extension id. It also matched the configured prefix list with a bare `startswith`,
    so `https://app.example.com` authorised `https://app.example.com.attacker.tld/`.

    The permissive branches are kept only as a local-development convenience: they need DEBUG
    and an empty allowlist, and they log a warning.
    """
    allowed_uris = getattr(settings, "INTEGRATION_ALLOWED_REDIRECT_URIS", [])
    if redirect_uri in allowed_uris:
        return True

    # Prefix match anchored at a path boundary, so a sibling domain cannot match.
    for prefix in getattr(settings, "INTEGRATION_ALLOWED_REDIRECT_URI_PREFIXES", []):
        if redirect_uri == prefix or redirect_uri.startswith(prefix.rstrip("/") + "/"):
            return True

    if allowed_uris:
        # An allowlist is configured, so anything outside it is refused regardless of DEBUG.
        return False

    if not settings.DEBUG:
        return False

    parsed = urlparse(redirect_uri)
    hostname = parsed.hostname or ""
    is_dev_redirect = (parsed.scheme in {"http", "https"} and hostname in {"localhost", "127.0.0.1"}) or (
        _is_allowed_client_id(client_id)
        and (
            parsed.scheme == "chrome-extension"
            or (parsed.scheme == "https" and hostname.endswith(".chromiumapp.org"))
        )
    )

    if is_dev_redirect:
        logger.warning(
            "Accepting integration redirect URI %s via the DEBUG-only fallback. "
            "Set INTEGRATION_ALLOWED_REDIRECT_URIS before deploying.",
            redirect_uri,
        )
    return is_dev_redirect


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _auth_code_ttl_seconds() -> int:
    return int(getattr(settings, "INTEGRATION_AUTH_CODE_TTL_SECONDS", DEFAULT_AUTH_CODE_TTL_SECONDS))


def _acquire_import_lock(lock_key: str) -> None:
    """Serialize concurrent imports of the same paper for the current transaction.

    Postgres advisory locks are released automatically at commit/rollback. On any other backend
    (SQLite in some test setups) this is a no-op and the endpoint falls back to the previous
    best-effort behaviour rather than erroring.
    """
    if connection.vendor != "postgresql":
        return
    # Two 32-bit keys: a fixed namespace plus a stable hash of the identifier.
    digest = hashlib.sha256(lock_key.encode("utf-8")).digest()
    key = int.from_bytes(digest[:4], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [IMPORT_LOCK_NAMESPACE, key])


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

    community_names = _requested_community_names(payload)
    visible_community_ids = _allowed_requested_community_ids(community_names, user)
    submission_type = "Private" if community_names else "Public"

    # Idempotency. The plugin sends a stable key per Zotero item and retries, so a replay must
    # return the original result rather than creating a second article. The identifier columns
    # are deliberately non-unique on this branch, so the database will not catch a duplicate for
    # us -- this cache plus the lock below is what makes the endpoint idempotent.
    idempotency_cache_key = (
        "integration-import:{}:{}:{}".format(
            user.id, ",".join(sorted(name.lower() for name in community_names)), payload.idempotency_key
        )
        if payload.idempotency_key
        else None
    )
    if idempotency_cache_key:
        cached_article_id = cache.get(idempotency_cache_key)
        if cached_article_id:
            cached = _visible_articles_for_user(
                Article.objects.filter(id=cached_article_id),
                user,
                community_ids=visible_community_ids,
            ).first()
            if cached:
                return _serialize_import(
                    cached, True, _attach_to_communities(cached, community_names, user)
                )

    identifier_matches = _identifier_matches(
        doi=doi,
        pmid=pmid,
        arxiv_id=arxiv_id,
        canonical_url=canonical_url,
        url=article_link,
        user=user,
        community_ids=visible_community_ids,
    )
    if len({match.id for match in identifier_matches.values()}) > 1:
        conflicting = ", ".join(sorted(identifier_matches))
        return 409, {
            "message": (
                f"The supplied identifiers ({conflicting}) refer to different papers on "
                "SciCommons. Please resolve the conflict before importing."
            )
        }

    # Serialize concurrent imports of the same paper. select_for_update cannot lock a row that
    # does not exist yet, so without this two simultaneous imports both find nothing and both
    # insert. An advisory lock keyed on the identifier closes that window without needing unique
    # constraints (and therefore without a data-cleanup migration).
    lock_key = doi or pmid or arxiv_id or canonical_url or article_link

    with transaction.atomic():
        if lock_key:
            _acquire_import_lock(lock_key)

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
                community_ids=visible_community_ids,
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
                submission_type=submission_type,
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

        community_results = _attach_to_communities(article, community_names, user)

    if idempotency_cache_key:
        cache.set(idempotency_cache_key, article.id, IMPORT_IDEMPOTENCY_TTL_SECONDS)

    return _serialize_import(article, found_existing, community_results)


@router.post(
    "/auth/authorize",
    response={200: IntegrationAuthorizeOut, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def authorize_integration(request, payload: IntegrationAuthorizeIn):
    # `client_id` is caller-supplied and was previously never validated -- any value minted a
    # usable code, since the only check was a hardcoded string compare inside the redirect test.
    if not _is_allowed_client_id(payload.client_id):
        return 400, {"message": "Unknown integration client."}

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
# Unauthenticated token endpoint: keyed by IP since there is no user yet.
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def exchange_integration_code(request, payload: IntegrationExchangeIn):
    # The whole read-check-consume sequence must hold a row lock. Without it, two concurrent
    # exchanges of the same code both saw `used_at IS NULL`, both passed PKCE and both minted a
    # full token pair -- `mark_used()` is an unconditional UPDATE, so the second was a silent
    # no-op rather than a conflict.
    with transaction.atomic():
        auth_code = (
            IntegrationAuthCode.objects.select_for_update()
            .select_related("user")
            .filter(code_hash=hash_secret(payload.code))
            .first()
        )
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
        user = auth_code.user

    # Minted after the row is committed as used, so a crash cannot leak an unconsumed token.
    return _token_payload(user)


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
# Unauthenticated and it INSERTs a row per call, so it was an open door to flooding the table.
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def start_device_auth(request, payload: DeviceStartIn):
    if not _is_allowed_client_id(payload.client_id):
        return 400, {"message": "Unknown integration client."}

    device_code = secrets.token_urlsafe(40)
    user_code = _generate_user_code()
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
# Rate limited because a wrong user_code is indistinguishable from an expired one, which
# otherwise makes this a free brute-force oracle for a 10-character code.
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="user_or_ip", rate="10/m", method="POST", block=True)
def approve_device_auth(request, payload: DeviceApproveIn):
    user_code = _normalize_user_code(payload.user_code)
    with transaction.atomic():
        query = IntegrationDeviceAuth.objects.select_for_update().filter(user_code_hash=hash_secret(user_code))
        if payload.client_id:
            query = query.filter(client_id=payload.client_id)
        device_auth = query.first()
        if device_auth is None or device_auth.is_expired:
            return 400, {"message": "Device authorization code is invalid or expired."}
        # Locked, so two users cannot both observe PENDING and race to bind their own account.
        if device_auth.status != IntegrationDeviceAuth.PENDING:
            return 400, {"message": "Device authorization code has already been used."}

        device_auth.approve(request.auth)
    return {"message": "SciCommons access approved."}


@router.post(
    "/auth/device/token",
    response={200: IntegrationTokenOut, 202: Message, 429: Message, codes_4xx: Message, codes_5xx: Message},
)
# Polled in a loop by design; the per-row interval check below is the primary control and
# this is the backstop against ignoring it entirely.
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
def exchange_device_token(request, payload: DeviceTokenIn):
    with transaction.atomic():
        device_auth = (
            # `of=("self",)` because `user` is nullable: select_related would make it the
            # nullable side of a LEFT JOIN, and Postgres rejects FOR UPDATE against that.
            IntegrationDeviceAuth.objects.select_for_update(of=("self",))
            .select_related("user")
            .filter(client_id=payload.client_id, device_code_hash=hash_secret(payload.device_code))
            .first()
        )
        if device_auth is None or device_auth.is_expired:
            return 400, {"message": "Device code is invalid or expired."}

        if device_auth.status == IntegrationDeviceAuth.PENDING:
            # Enforce the advertised poll interval instead of merely advertising it. RFC 8628
            # calls this `slow_down`; clients that ignore `interval` were previously free to
            # hammer this unauthenticated endpoint.
            too_soon = device_auth.last_polled_at and timezone.now() - device_auth.last_polled_at < timedelta(
                seconds=device_auth.interval_seconds
            )
            device_auth.mark_polled()
            if too_soon:
                return 429, {"message": "Polling too frequently. Slow down."}
            return 202, {"message": "Authorization pending."}

        if device_auth.status == IntegrationDeviceAuth.CONSUMED or device_auth.user is None:
            return 400, {"message": "Device code has already been used."}

        user = device_auth.user
        # Consume BEFORE minting: previously the token was built first, so two concurrent polls
        # could both mint before either wrote CONSUMED. Capture the FK object first because
        # `consume()` saves the row and can invalidate the nullable `user` relation cache.
        device_auth.consume()

    return _token_payload(user)
