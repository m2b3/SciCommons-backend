from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django_redis import get_redis_connection


class CacheOperationError(Exception):
    pass

def get_cache(key, default=None, version=None, cache_name='default'):
    """Safe cache retrieval with enhanced error handling"""
    try:
        if not isinstance(key, str):
            raise ValueError("Cache key must be string")

        return caches[cache_name].get(key, default=default, version=version)
    except InvalidCacheBackendError as e:
        return default
    except Exception as e:
        return default

def set_cache(key, value, timeout=None, version=None, cache_name='default'):
    """Cache setter with timeout handling and validation"""
    try:
        if not isinstance(key, str):
            raise ValueError("Cache key must be string")
            
        caches[cache_name].set(key, value, timeout=timeout, version=version)
        return True
    except Exception as e:
        raise CacheOperationError(f"Cache set failed: {str(e)}")

def set_cache_with_tags(key, value, timeout=None, version=None, cache_name='default', tags=None):
    """Set cache with article IDs as tags."""
    try:
        if not isinstance(key, str):
            raise ValueError("Cache key must be a string")

        # Get the cache backend
        cache = caches[cache_name]

        # Use the standard set method to store the value in cache
        cache.set(key, value, timeout=timeout, version=version)

        # For Redis-based caches, add tags (article IDs) as additional cache keys.
        if tags:
            redis_cache = get_redis_connection("default")
            for tag in tags:
                redis_cache.sadd(f"cache_tag:{tag}", key)

        return True

    except InvalidCacheBackendError as e:
        raise CacheOperationError(f"Invalid cache backend: {str(e)}")
    except ValueError as e:
        raise CacheOperationError(f"Value error: {str(e)}")
    except Exception as e:
        raise CacheOperationError(f"Cache operation failed: {str(e)}")

def delete_cache(key, version=None, cache_name='default'):
    """Idempotent cache deletion with error suppression"""
    try:
        caches[cache_name].delete(key, version=version)
        return True
    except Exception as e:
        return False

def invalidate_cache_with_tags(tags, cache_name='default'):
    """Invalidate cache entries associated with the given article IDs."""
    try:
        if not isinstance(tags, (list, set, tuple)):
            raise ValueError("tags must be a list, set, or tuple")

        redis_cache = get_redis_connection("default")

        for tag in tags:
            tag_key = f"cache_tag:{tag}"
            keys = redis_cache.smembers(tag_key)

            if keys:
                redis_cache.delete(*keys)  # Delete all cache keys
                redis_cache.delete(tag_key)  # Optionally delete the tag set itself

        return True

    except InvalidCacheBackendError as e:
        raise CacheOperationError(f"Invalid cache backend: {str(e)}")
    except ValueError as e:
        raise CacheOperationError(f"Value error: {str(e)}")
    except Exception as e:
        raise CacheOperationError(f"Cache invalidation failed: {str(e)}")