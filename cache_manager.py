"""
Persistent Cache Manager for Media Recommendation System

Provides disk-based caching with TTL support to maintain cache data
across application restarts. Thread-safe and supports automatic cleanup
of expired entries.
"""

import json
import os
import time
import threading
import logging
from typing import Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class PersistentCacheManager:
    """
    Thread-safe persistent cache manager that stores data in JSON files.
    
    Features:
    - Automatic save/load from disk
    - TTL-based expiration
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Debounced disk writes to reduce I/O
    """
    
    def __init__(self, cache_file: str, cache_dir: str = ".cache"):
        """
        Initialize the persistent cache manager.
        
        Args:
            cache_file: Name of the cache file (e.g., 'api_cache.json')
            cache_dir: Directory to store cache files (default: '.cache')
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / cache_file
        self.lock = threading.RLock()
        self._cache = {}
        self._dirty = False
        self._last_save_time = 0
        self.SAVE_DEBOUNCE_SECONDS = 1  # Reduced to 1s to prevent data loss in short runs
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load existing cache
        self._load_from_disk()
        
        logger.info(f"PersistentCacheManager initialized: {self.cache_file}")
    
    def _load_from_disk(self):
        """Load cache data from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Validate and load cache entries
                    for key, value in data.items():
                        if isinstance(value, list) and len(value) == 2:
                            self._cache[key] = tuple(value)  # (timestamp, data)
                logger.info(f"Loaded {len(self._cache)} entries from {self.cache_file}")
            else:
                # Initialize empty file immediately to prevent "missing file" confusion
                self._save_to_disk(force=True)
                logger.info(f"Created new cache file at {self.cache_file}")
        except Exception as e:
            logger.error(f"Error loading cache from disk: {e}")
            self._cache = {}
    
    def _save_to_disk(self, force: bool = False):
        """
        Save cache data to disk.
        
        Args:
            force: If True, save immediately. Otherwise use debouncing.
        """
        current_time = time.time()
        
        # Debounce: only save if enough time has passed or forced
        if not force and (current_time - self._last_save_time) < self.SAVE_DEBOUNCE_SECONDS:
            self._dirty = True  # Mark as dirty for later save
            return
        
        try:
            # Convert tuples to lists for JSON serialization
            serializable_cache = {
                key: list(value) for key, value in self._cache.items()
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
            
            self._last_save_time = current_time
            self._dirty = False
            logger.debug(f"Saved {len(self._cache)} entries to {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving cache to disk: {e}")
    
    def get(self, key: str, ttl: int = None) -> Optional[Any]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: Cache key
            ttl: Time-to-live in seconds. If provided and entry is older, returns None
            
        Returns:
            Cached value if found and not expired, None otherwise
        """
        with self.lock:
            if key not in self._cache:
                return None
            
            cache_time, value = self._cache[key]
            
            # Check if expired
            if ttl is not None and (time.time() - cache_time) >= ttl:
                # Remove expired entry
                del self._cache[key]
                self._dirty = True
                return None
            
            return value
    
    def set(self, key: str, value: Any):
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        with self.lock:
            self._cache[key] = (time.time(), value)
            # Force save immediately to prevent data loss on interruption
            self._save_to_disk(force=True)
    
    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self._cache.clear()
            self._save_to_disk(force=True)
            logger.info(f"Cleared cache: {self.cache_file}")
    
    def cleanup_expired(self, ttl: int):
        """
        Remove all expired entries from the cache.
        
        Args:
            ttl: Time-to-live in seconds
        """
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, (cache_time, _) in self._cache.items()
                if (current_time - cache_time) >= ttl
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self._save_to_disk(force=True)
                logger.info(f"Cleaned up {len(expired_keys)} expired entries from {self.cache_file}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self.lock:
            return {
                'total_entries': len(self._cache),
                'cache_file': str(self.cache_file),
                'file_exists': self.cache_file.exists()
            }
    
    def __del__(self):
        """Ensure cache is saved when object is destroyed."""
        if self._dirty:
            self._save_to_disk(force=True)
