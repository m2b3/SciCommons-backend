"""
User settings cache service with Redis.

This module provides caching for user settings with:
- Immediate cache invalidation on settings change
- Fallback to database on cache miss
- Helper functions for checking specific settings
- Graceful degradation if Redis is unavailable
"""

import logging
from typing import Any, Dict, Optional

from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError

from users.config_constants import (
    UserConfigKey,
    get_all_config_metadata,
    get_default_value,
)

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_NAME = "default"
USER_SETTINGS_CACHE_PREFIX = "user_settings"
# Cache TTL: 1 hour - settings don't change frequently but we want
# reasonable freshness. Invalidation handles immediate updates.
USER_SETTINGS_CACHE_TTL = 3600  # 1 hour


def _get_cache_key(user_id: int) -> str:
    """
    Generate a cache key for user settings.

    Args:
        user_id: The user's ID

    Returns:
        Cache key string
    """
    return f"{USER_SETTINGS_CACHE_PREFIX}:{user_id}"


def _get_cache():
    """Get the cache backend, returns None if unavailable."""
    try:
        return caches[CACHE_NAME]
    except InvalidCacheBackendError:
        logger.warning("Cache backend not available")
        return None


def get_user_settings_from_cache(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user settings from cache.

    Args:
        user_id: The user's ID

    Returns:
        Dictionary of settings or None if not in cache
    """
    cache = _get_cache()
    if cache is None:
        return None

    try:
        cache_key = _get_cache_key(user_id)
        return cache.get(cache_key)
    except Exception as e:
        logger.error(f"Error getting user settings from cache: {e}")
        return None


def set_user_settings_in_cache(user_id: int, settings: Dict[str, Any]) -> bool:
    """
    Set user settings in cache.

    Args:
        user_id: The user's ID
        settings: Dictionary of settings to cache

    Returns:
        True if successful, False otherwise
    """
    cache = _get_cache()
    if cache is None:
        return False

    try:
        cache_key = _get_cache_key(user_id)
        cache.set(cache_key, settings, timeout=USER_SETTINGS_CACHE_TTL)
        logger.debug(f"Cached settings for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting user settings in cache: {e}")
        return False


def invalidate_user_settings_cache(user_id: int) -> bool:
    """
    Invalidate (delete) user settings from cache.
    Should be called whenever settings are updated or reset.

    Args:
        user_id: The user's ID

    Returns:
        True if successful, False otherwise
    """
    cache = _get_cache()
    if cache is None:
        return False

    try:
        cache_key = _get_cache_key(user_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated settings cache for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error invalidating user settings cache: {e}")
        return False


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """
    Get all user settings with caching.
    Tries cache first, falls back to database, then caches the result.

    Args:
        user_id: The user's ID

    Returns:
        Dictionary of all settings with their values
    """
    # Import here to avoid circular imports
    from users.models import UserSetting

    # Try cache first
    cached_settings = get_user_settings_from_cache(user_id)
    if cached_settings is not None:
        logger.debug(f"Cache hit for user {user_id} settings")
        return cached_settings

    logger.debug(f"Cache miss for user {user_id} settings, fetching from DB")

    # Get all config metadata for defaults
    config_metadata = get_all_config_metadata()

    # Get user's custom settings from database
    try:
        user_settings = UserSetting.objects.filter(user_id=user_id)
        user_settings_dict = {
            setting.config_name: setting.value for setting in user_settings
        }
    except Exception as e:
        logger.error(f"Error fetching user settings from DB: {e}")
        user_settings_dict = {}

    # Merge with defaults (user settings override defaults)
    all_settings = {}
    for config_name, metadata in config_metadata.items():
        all_settings[config_name] = user_settings_dict.get(
            config_name, metadata["default_value"]
        )

    # Cache the result
    set_user_settings_in_cache(user_id, all_settings)

    return all_settings


def get_user_setting(user_id: int, config_key: str) -> Any:
    """
    Get a specific user setting value.

    Args:
        user_id: The user's ID
        config_key: The configuration key (use UserConfigKey enum)

    Returns:
        The setting value (user's value or default)
    """
    settings = get_user_settings(user_id)
    return settings.get(config_key, get_default_value(config_key))


# ============================================================================
# Helper functions for checking specific settings
# These are the primary interface for other parts of the application
# ============================================================================


def is_email_notifications_enabled(user_id: int) -> bool:
    """
    Check if email notifications are enabled for a user.

    Args:
        user_id: The user's ID

    Returns:
        True if email notifications are enabled, False otherwise
    """
    return bool(get_user_setting(user_id, UserConfigKey.ENABLE_EMAIL_NOTIFICATIONS))


def is_sound_on_discussion_notification_enabled(user_id: int) -> bool:
    """
    Check if sound on discussion notification is enabled for a user.

    Args:
        user_id: The user's ID

    Returns:
        True if sound is enabled, False otherwise
    """
    return bool(
        get_user_setting(user_id, UserConfigKey.ENABLE_SOUND_ON_DISCUSSION_NOTIFICATION)
    )


# ============================================================================
# Bulk operations for efficiency
# ============================================================================


def get_users_with_email_notifications_enabled(user_ids: list[int]) -> list[int]:
    """
    Filter a list of user IDs to only those with email notifications enabled.
    Useful for batch operations like sending notifications to multiple users.

    Args:
        user_ids: List of user IDs to check

    Returns:
        List of user IDs that have email notifications enabled
    """
    return [user_id for user_id in user_ids if is_email_notifications_enabled(user_id)]


def prefetch_user_settings(user_ids: list[int]) -> Dict[int, Dict[str, Any]]:
    """
    Prefetch and cache settings for multiple users.
    Useful for batch operations to avoid N+1 queries.

    Args:
        user_ids: List of user IDs to prefetch

    Returns:
        Dictionary mapping user_id to their settings
    """
    # Import here to avoid circular imports
    from users.models import UserSetting

    result = {}
    users_to_fetch = []

    # Check cache first for each user
    for user_id in user_ids:
        cached = get_user_settings_from_cache(user_id)
        if cached is not None:
            result[user_id] = cached
        else:
            users_to_fetch.append(user_id)

    if not users_to_fetch:
        return result

    # Fetch all uncached settings in one query
    config_metadata = get_all_config_metadata()

    try:
        all_user_settings = UserSetting.objects.filter(user_id__in=users_to_fetch)

        # Group by user_id
        settings_by_user: Dict[int, Dict[str, Any]] = {
            user_id: {} for user_id in users_to_fetch
        }
        for setting in all_user_settings:
            settings_by_user[setting.user_id][setting.config_name] = setting.value

        # Merge with defaults and cache
        for user_id in users_to_fetch:
            user_settings = {}
            for config_name, metadata in config_metadata.items():
                user_settings[config_name] = settings_by_user[user_id].get(
                    config_name, metadata["default_value"]
                )
            result[user_id] = user_settings
            set_user_settings_in_cache(user_id, user_settings)

    except Exception as e:
        logger.error(f"Error prefetching user settings: {e}")
        # Return defaults for users we couldn't fetch
        for user_id in users_to_fetch:
            if user_id not in result:
                result[user_id] = {
                    config_name: metadata["default_value"]
                    for config_name, metadata in config_metadata.items()
                }

    return result
