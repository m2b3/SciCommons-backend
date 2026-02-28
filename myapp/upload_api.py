"""
API endpoints for image uploads to S3.

Upload pattern:
1. Frontend sends image to backend -> Backend uploads to S3 -> Returns URL
2. User inserts URL into markdown editor
3. When content is submitted, async handler increments ref_count for used images
4. Orphaned images (ref_count=0) can be cleaned up periodically
"""

import logging
import re
import time
import uuid
from typing import List, Set
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from django.conf import settings
from django.db.models import F
from django_ratelimit.decorators import ratelimit
from ninja import File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile as NinjaUploadedFile

from users.auth import JWTAuth
from users.models import UploadedImage

logger = logging.getLogger(__name__)

router = Router(tags=["Uploads"])


# =============================================================================
# Constants
# =============================================================================

MAX_IMAGE_SIZE_BYTES = 500 * 1024  # 500KB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}

ALLOWED_ORIGINS = [
    "https://scicommons.org",
    "https://www.scicommons.org",
    "https://test.scicommons.org",
    "https://alphatest.scicommons.org",
]
if settings.DEBUG:
    ALLOWED_ORIGINS.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )


# =============================================================================
# Schemas
# =============================================================================


class UploadImageResponse(Schema):
    """Response schema for image upload."""

    object_key: str
    public_url: str


# =============================================================================
# Origin Validation
# =============================================================================


def validate_origin(request) -> bool:
    """
    Validate that the request comes from an allowed origin.

    Checks both Origin and Referer headers to handle various browser behaviors.
    """
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")

    for allowed in ALLOWED_ORIGINS:
        if origin == allowed:
            return True
        if referer:
            parsed_referer = urlparse(referer)
            referer_origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
            if referer_origin == allowed:
                return True

    return False


# =============================================================================
# S3 Client & Helper Functions
# =============================================================================


def get_s3_client():
    """Create boto3 S3 client configured for Arbutus Object Storage."""
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(
            signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
        ),
    )


def generate_object_key(user_id: int, content_type: str) -> str:
    """
    Generate unique S3 object key.

    Format: user-attachments/{ENVIRONMENT}/{user_id}_user_{uuid}_{timestamp}.{ext}
    Example: user-attachments/prod/7_user_55b31315_1768284442.jpg
    """
    extension = ALLOWED_IMAGE_TYPES.get(content_type, ".jpg")
    unique_id = uuid.uuid4().hex[:8]
    timestamp = int(time.time())

    filename = f"{user_id}_user_{unique_id}_{timestamp}{extension}"
    return f"user-attachments/{settings.ENVIRONMENT}/{filename}"


def build_public_url(object_key: str) -> str:
    """
    Build public URL for an uploaded file.

    Format: https://{AWS_S3_CUSTOM_DOMAIN}/{object_key}
    """
    return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{object_key}"


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/image",
    response=UploadImageResponse,
    auth=JWTAuth(),
    summary="Upload an image for markdown editor",
)
@ratelimit(key="user", rate="30/m", method="POST", block=True)
def upload_image(request, file: NinjaUploadedFile = File(...)):
    """
    Upload an image to S3 for use in markdown editors.

    **Size Limit:** 500KB

    **Allowed Types:** image/jpeg, image/png, image/gif, image/webp

    **Rate Limit:** 30 uploads per minute per user

    **Origin Restriction:** Only requests from scicommons.org domains are allowed.

    Images are stored in `user-attachments/{env}/` with ref_count=0.
    When the image is used in submitted content, ref_count is incremented.
    Orphaned images (ref_count=0) can be cleaned up periodically.

    **Frontend Usage:**
    ```javascript
    const formData = new FormData();
    formData.append('file', imageFile);

    const response = await fetch('/api/uploads/image', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer <token>' },
        body: formData
    });
    const { public_url } = await response.json();

    // Insert into markdown editor
    editor.insertText(`![image](${public_url})`);
    ```
    """
    if not validate_origin(request):
        logger.warning(
            f"Upload rejected: invalid origin. "
            f"Origin={request.headers.get('Origin')}, "
            f"Referer={request.headers.get('Referer')}"
        )
        raise HttpError(403, "Upload not allowed from this origin")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HttpError(
            400,
            f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES.keys())}",
        )

    if file.size > MAX_IMAGE_SIZE_BYTES:
        raise HttpError(
            400,
            f"File too large. Maximum size: {MAX_IMAGE_SIZE_BYTES // 1024}KB",
        )

    object_key = generate_object_key(request.auth.id, file.content_type)

    try:
        s3_client = get_s3_client()

        extra_args = {"ContentType": file.content_type}
        if settings.AWS_DEFAULT_ACL:
            extra_args["ACL"] = settings.AWS_DEFAULT_ACL

        s3_client.upload_fileobj(
            file.file,
            settings.AWS_STORAGE_BUCKET_NAME,
            object_key,
            ExtraArgs=extra_args,
        )

        public_url = build_public_url(object_key)

        UploadedImage.objects.create(
            user=request.auth,
            object_key=object_key,
            content_type=file.content_type,
            file_size=file.size,
            ref_count=0,
        )

        logger.info(f"User {request.auth.id} uploaded image: {object_key}")

        return UploadImageResponse(object_key=object_key, public_url=public_url)

    except Exception as e:
        logger.error(f"Failed to upload image: {e}")
        raise HttpError(500, "Failed to upload image")


# =============================================================================
# Image Reference Tracking
# =============================================================================


def extract_image_object_keys(markdown_content: str) -> Set[str]:
    """
    Extract S3 object keys from user-attachment image URLs in markdown content.

    Matches URLs like:
    - https://cdn.scicommons.org/user-attachments/prod/7_user_55b31315_1768284442.jpg
    - https://cdn.scicommons.org/user-attachments/local/123_user_abc12345_1234567890.png?query=param
    - https://cdn.scicommons.org/user-attachments/test/1_user_def67890_9876543210.gif#anchor

    The regex handles:
    - Different environments (prod, test, local, etc.)
    - Various image extensions (.jpg, .jpeg, .png, .gif, .webp)
    - Extra URL parameters, query strings, anchors, etc.
    - URLs embedded in markdown image syntax ![alt](url) or plain URLs

    Returns a set of object keys (e.g., "user-attachments/prod/7_user_55b31315_1768284442.jpg")
    """
    pattern = re.compile(
        r"https://cdn\.scicommons\.org/"
        r"(user-attachments/[a-zA-Z0-9_-]+/\d+_user_[a-f0-9]+_\d+\.(?:jpg|jpeg|png|gif|webp|avif))"
        r"(?:[?#][^\s\)\"\']*)?",
        re.IGNORECASE,
    )

    matches = pattern.findall(markdown_content)
    return set(matches)


def increment_image_ref_counts(object_keys: Set[str]) -> int:
    """
    Increment ref_count for multiple images in a single efficient query.

    Uses Django's F() expression for atomic increment and bulk update.
    Silently skips keys that don't exist in the database.

    Args:
        object_keys: Set of S3 object keys to increment ref_count for

    Returns:
        Number of images successfully updated
    """
    if not object_keys:
        return 0

    updated_count = UploadedImage.objects.filter(object_key__in=object_keys).update(
        ref_count=F("ref_count") + 1
    )

    if updated_count < len(object_keys):
        logger.warning(
            f"Some image keys not found. Expected: {len(object_keys)}, "
            f"Updated: {updated_count}"
        )

    return updated_count


def process_content_images_async(markdown_content: str) -> None:
    """
    Asynchronously extract image URLs from markdown and increment ref_counts.

    This is the main function to call when content (comment, review, etc.)
    is submitted. It spawns a background thread to process the images,
    so it doesn't block the request thread.

    Args:
        markdown_content: The markdown string containing potential image URLs

    Example usage:
        # In your comment/review submission handler:
        from myapp.upload_api import process_content_images_async

        def submit_comment(request, content: str):
            # ... save comment logic ...
            process_content_images_async(content)
    """
    if not markdown_content:
        return

    import threading

    def _process():
        try:
            object_keys = extract_image_object_keys(markdown_content)
            if object_keys:
                logger.info(f"Processing {len(object_keys)} image references")
                increment_image_ref_counts(object_keys)
        except Exception as e:
            logger.error(f"Failed to process image references: {e}")

    thread = threading.Thread(target=_process, daemon=True)
    thread.start()
