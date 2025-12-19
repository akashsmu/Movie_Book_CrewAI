"""Caching decorator for API calls."""

import functools
import time
import logging
from cache_manager import PersistentCacheManager

# Module logger
logger = logging.getLogger(__name__)

# Persistent cache for API responses
_api_cache = PersistentCacheManager('api_cache.json')


def cache_api_call(ttl: int = 300):
    """
    Decorator to cache API call results.
    
    Args:
        ttl: Time to live in seconds (default: 300 = 5 minutes)
        
    Returns:
        Decorated function with caching
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create deterministic cache key
            # If this is a bound method, drop `self` from the args when forming the key
            key_args = args[1:] if (len(args) > 0 and hasattr(args[0], '__class__')) else args
            
            # Sort kwargs to ensure deterministic key regardless of dict order
            sorted_kwargs = dict(sorted(kwargs.items()))
            cache_key = f"{func.__name__}:{str(key_args)}:{str(sorted_kwargs)}"

            # Check cache using persistent manager
            cached_result = _api_cache.get(cache_key, ttl=ttl)
            if cached_result is not None:
                logger.debug(f"cache_api_call: HIT {cache_key}")
                return cached_result
            else:
                logger.debug(f"cache_api_call: MISS {cache_key}")

            # Call function and cache result
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"cache_api_call: CALL {func.__name__} took {duration:.3f}s")
            _api_cache.set(cache_key, result)
            return result
        return wrapper
    return decorator
