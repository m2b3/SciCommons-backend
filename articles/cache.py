import logging

from myapp.cache import delete_cache

logger = logging.getLogger(__name__)


def generate_articles_cache_key(
    community_id=None, search=None, sort=None, rating=None, page=1, per_page=10
):
    """Generate cache key for articles list based on parameters"""
    key_parts = ["articles"]

    if community_id:
        key_parts.append(f"community_{community_id}")

    if search:
        key_parts.append(f"search_{search}")

    if sort:
        key_parts.append(f"sort_{sort}")

    if rating:
        key_parts.append(f"rating_{rating}")

    key_parts.extend([f"page_{page}", f"per_page_{per_page}"])

    return "_".join(key_parts)


def invalidate_articles_cache():
    """Invalidate common article cache keys"""
    try:
        # Common cache keys to invalidate
        common_keys = [
            "articles_page_1_per_page_10",  # Default pagination
            "articles_page_1_per_page_20",  # Common pagination variations
            "articles_sort_latest_page_1_per_page_10",
            "articles_sort_older_page_1_per_page_10",
        ]

        for key in common_keys:
            delete_cache(key)

        # Also clear first few pages for different page sizes
        for page in range(1, 6):  # Clear first 5 pages
            for per_page in [10, 20, 50]:  # Common page sizes
                keys_to_clear = [
                    f"articles_page_{page}_per_page_{per_page}",
                    f"articles_sort_latest_page_{page}_per_page_{per_page}",
                    f"articles_sort_older_page_{page}_per_page_{per_page}",
                ]
                for key in keys_to_clear:
                    delete_cache(key)

        logger.debug("Successfully invalidated articles cache")
    except Exception as e:
        logger.warning(f"Failed to invalidate articles cache: {e}")
