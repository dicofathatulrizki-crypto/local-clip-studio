"""PluginCache — caches loaded plugin instances and manifests for fast retrieval.

Supports:
- Instance caching with TTL
- Manifest caching
- Cache invalidation by plugin ID
- Full cache clear
- LRU-based eviction
"""
from __future__ import annotations

import time
from typing import Any

from backend.infrastructure.plugins.types import PluginCacheEntry, PluginManifest


class PluginCache:
    """LRU cache for loaded plugin instances and manifests.

    Usage:
        cache = PluginCache(max_size=100)
        cache.set("my-plugin", instance)
        instance = cache.get("my-plugin")
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._entries: dict[str, PluginCacheEntry] = {}
        self._access_order: list[str] = []

    def get(self, plugin_id: str) -> Any | None:
        """Get a cached plugin instance.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Cached instance, or None if not cached or expired.
        """
        entry = self._entries.get(plugin_id)
        if entry is None:
            return None

        # Check TTL
        if self._ttl > 0 and (time.time() - entry.cached_at) > self._ttl:
            self.remove(plugin_id)
            return None

        # Update access order
        self._touch(plugin_id)
        return entry.instance

    def set(self, plugin_id: str, instance: Any, manifest: PluginManifest | None = None) -> None:
        """Cache a plugin instance.

        Args:
            plugin_id: The plugin ID.
            instance: The plugin instance to cache.
            manifest: Optional manifest to cache alongside.
        """
        # Evict if at capacity
        if len(self._entries) >= self._max_size:
            self._evict_lru()

        entry = PluginCacheEntry(
            instance=instance,
            manifest=manifest,
            cached_at=time.time(),
            valid=True,
        )
        self._entries[plugin_id] = entry
        self._touch(plugin_id)

    def remove(self, plugin_id: str) -> None:
        """Remove a plugin from the cache.

        Args:
            plugin_id: The plugin ID to remove.
        """
        self._entries.pop(plugin_id, None)
        if plugin_id in self._access_order:
            self._access_order.remove(plugin_id)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._entries.clear()
        self._access_order.clear()

    def exists(self, plugin_id: str) -> bool:
        """Check if a plugin is in the cache.

        Args:
            plugin_id: The plugin ID.

        Returns:
            True if cached and not expired.
        """
        entry = self._entries.get(plugin_id)
        if entry is None:
            return False
        if self._ttl > 0 and (time.time() - entry.cached_at) > self._ttl:
            self.remove(plugin_id)
            return False
        return True

    def get_manifest(self, plugin_id: str) -> PluginManifest | None:
        """Get a cached manifest.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Cached manifest, or None.
        """
        entry = self._entries.get(plugin_id)
        return entry.manifest if entry else None

    def size(self) -> int:
        """Get the current number of cached entries.

        Returns:
            Cache entry count.
        """
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        """Check if the cache is empty.

        Returns:
            True if no entries are cached.
        """
        return len(self._entries) == 0

    # ─── Private ────────────────────────────────────────────────

    def _touch(self, plugin_id: str) -> None:
        """Update access order for a plugin ID."""
        if plugin_id in self._access_order:
            self._access_order.remove(plugin_id)
        self._access_order.append(plugin_id)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._access_order:
            oldest = self._access_order.pop(0)
            self._entries.pop(oldest, None)
