"""PluginRegistry — the central registry for all plugins in the system.

Provides:
- register, unregister, enable, disable
- activate, deactivate
- Query by capability, type, version, health status
- Dependency graph and statistics
- get_best_provider(task_type) for routing
"""
from __future__ import annotations

import time
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.errors import (
    PluginCapabilityError,
    PluginNotFoundError,
    PluginRuntimeError,
)
from backend.infrastructure.plugins.lifecycle import PluginLifecycleManager
from backend.infrastructure.plugins.types import (
    DependencyGraph,
    PluginInfo,
    PluginInstance,
    PluginManifest,
    PluginRegistration,
    PluginState,
    PluginType,
)

logger = get_logger(__name__)


class PluginRegistry:
    """Central registry for plugin lifecycle and query management.

    Usage:
        registry = PluginRegistry()
        registry.register(instance)
        provider = registry.get_best_provider(PluginType.STT)
        plugins = registry.query_by_capability("diarization")
    """

    def __init__(self, lifecycle_manager: PluginLifecycleManager | None = None) -> None:
        self._registrations: dict[str, PluginRegistration] = {}
        self._lifecycle = lifecycle_manager or PluginLifecycleManager()

    # ─── Registration ──────────────────────────────────────────

    def register(self, instance: PluginInstance) -> None:
        """Register a plugin instance in the registry.

        Args:
            instance: The plugin instance to register.
        """
        now = time.time()
        plugin_id = instance.manifest.id

        if plugin_id in self._registrations:
            logger.info("Updating existing plugin registration", extra={"plugin_id": plugin_id})
            self._registrations[plugin_id].updated_at = now
            self._registrations[plugin_id].instance = instance
        else:
            self._registrations[plugin_id] = PluginRegistration(
                instance=instance,
                registered_at=now,
                updated_at=now,
            )
            logger.info(
                "Plugin registered",
                extra={
                    "plugin_id": plugin_id,
                    "type": instance.manifest.plugin_type.value,
                    "version": instance.manifest.version,
                },
            )

    def unregister(self, plugin_id: str) -> None:
        """Unregister a plugin from the registry.

        Args:
            plugin_id: The plugin ID to unregister.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        self._check_exists(plugin_id)
        instance = self._registrations[plugin_id].instance

        # Shut down if active
        if instance.state in (PluginState.ACTIVE, PluginState.INITIALIZED):
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(
                    self._lifecycle.shutdown(instance)
                )
            except RuntimeError:
                pass  # No event loop running

        del self._registrations[plugin_id]
        logger.info("Plugin unregistered", extra={"plugin_id": plugin_id})

    def register_batch(self, instances: list[PluginInstance]) -> None:
        """Register multiple plugin instances at once.

        Args:
            instances: List of plugin instances.
        """
        for instance in instances:
            self.register(instance)

    # ─── Enable / Disable ──────────────────────────────────────

    def enable(self, plugin_id: str) -> None:
        """Enable a plugin.

        Args:
            plugin_id: The plugin ID to enable.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        self._check_exists(plugin_id)
        instance = self._registrations[plugin_id].instance
        instance.enabled = True
        logger.info("Plugin enabled", extra={"plugin_id": plugin_id})

    def disable(self, plugin_id: str) -> None:
        """Disable a plugin.

        Args:
            plugin_id: The plugin ID to disable.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        self._check_exists(plugin_id)
        instance = self._registrations[plugin_id].instance
        instance.enabled = False
        logger.info("Plugin disabled", extra={"plugin_id": plugin_id})

    def is_enabled(self, plugin_id: str) -> bool:
        """Check if a plugin is enabled.

        Args:
            plugin_id: The plugin ID.

        Returns:
            True if enabled.
        """
        reg = self._registrations.get(plugin_id)
        return reg is not None and reg.instance.enabled

    # ─── Activate / Deactivate ─────────────────────────────────

    async def activate(self, plugin_id: str) -> None:
        """Activate a registered plugin.

        Args:
            plugin_id: The plugin ID.

        Raises:
            PluginNotFoundError: If not registered.
        """
        self._check_exists(plugin_id)
        instance = self._registrations[plugin_id].instance
        await self._lifecycle.activate(instance)
        logger.info("Plugin activated", extra={"plugin_id": plugin_id})

    async def deactivate(self, plugin_id: str) -> None:
        """Deactivate an active plugin.

        Args:
            plugin_id: The plugin ID.

        Raises:
            PluginNotFoundError: If not registered.
        """
        self._check_exists(plugin_id)
        instance = self._registrations[plugin_id].instance
        await self._lifecycle.deactivate(instance)
        logger.info("Plugin deactivated", extra={"plugin_id": plugin_id})

    # ─── Query ──────────────────────────────────────────────

    def get(self, plugin_id: str) -> PluginInstance:
        """Get a plugin instance by ID.

        Args:
            plugin_id: The plugin ID.

        Returns:
            PluginInstance.

        Raises:
            PluginNotFoundError: If not registered.
        """
        self._check_exists(plugin_id)
        return self._registrations[plugin_id].instance

    def get_info(self, plugin_id: str) -> PluginInfo:
        """Get public plugin info for API responses.

        Args:
            plugin_id: The plugin ID.

        Returns:
            PluginInfo with filtered data.
        """
        instance = self.get(plugin_id)
        manifest = instance.manifest
        return PluginInfo(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            plugin_type=manifest.plugin_type.value,
            author=manifest.author,
            description=manifest.description,
            state=instance.state.value,
            enabled=instance.enabled,
            capabilities=list(manifest.capabilities),
            permissions=[p.value for p in manifest.permissions],
            health_status=instance.health_status,
            error_message=instance.error_message,
            config_schema=dict(manifest.config_schema),
        )

    def list_all(self) -> list[PluginInstance]:
        """Get all registered plugin instances.

        Returns:
            List of all PluginInstance objects.
        """
        return [reg.instance for reg in self._registrations.values()]

    def list_enabled(self) -> list[PluginInstance]:
        """Get all enabled plugin instances.

        Returns:
            List of enabled PluginInstance objects.
        """
        return [
            reg.instance
            for reg in self._registrations.values()
            if reg.instance.enabled
        ]

    def list_by_state(self, state: PluginState) -> list[PluginInstance]:
        """Get all plugins in a specific state.

        Args:
            state: The plugin state to filter by.

        Returns:
            List of matching PluginInstance objects.
        """
        return [
            reg.instance
            for reg in self._registrations.values()
            if reg.instance.state == state
        ]

    def query_by_type(self, plugin_type: PluginType) -> list[PluginInstance]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: The plugin type.

        Returns:
            List of matching PluginInstance objects.
        """
        return [
            reg.instance
            for reg in self._registrations.values()
            if reg.instance.manifest.plugin_type == plugin_type
        ]

    def query_by_capability(self, capability: str) -> list[PluginInstance]:
        """Get all plugins that support a specific capability.

        Args:
            capability: The capability string.

        Returns:
            List of matching PluginInstance objects.
        """
        return [
            reg.instance
            for reg in self._registrations.values()
            if capability in reg.instance.manifest.capabilities
        ]

    def query_by_version(self, version: str) -> list[PluginInstance]:
        """Get all plugins with a specific version.

        Args:
            version: The version string.

        Returns:
            List of matching PluginInstance objects.
        """
        return [
            reg.instance
            for reg in self._registrations.values()
            if reg.instance.manifest.version == version
        ]

    # ─── Provider Routing ──────────────────────────────────

    def get_best_provider(self, task_type: PluginType, require_capability: str | None = None) -> PluginInstance:
        """Get the best available provider for a task type.

        Selects the highest-priority enabled plugin that supports
        the required capability.

        Args:
            task_type: The type of plugin needed (STT, LLM, VISION, etc.).
            require_capability: Optional required capability.

        Returns:
            The best matching PluginInstance.

        Raises:
            PluginNotFoundError: If no suitable provider is found.
            PluginCapabilityError: If no provider supports the required capability.
        """
        candidates: list[PluginInstance] = []

        for reg in self._registrations.values():
            instance = reg.instance
            if not instance.enabled:
                continue
            if instance.state not in (PluginState.ACTIVE, PluginState.INITIALIZED):
                continue
            if instance.manifest.plugin_type != task_type:
                continue
            if require_capability and require_capability not in instance.manifest.capabilities:
                continue
            candidates.append(instance)

        if not candidates:
            msg = f"No enabled provider available for task type '{task_type.value}'"
            if require_capability:
                msg += f" with capability '{require_capability}'"
            raise PluginNotFoundError(msg)

        # Sort by priority (lower = better), then by name
        candidates.sort(key=lambda p: (p.priority, p.manifest.name))
        return candidates[0]

    def get_providers_for_task(self, task_type: PluginType) -> list[PluginInstance]:
        """Get all providers for a task type, sorted by priority.

        Args:
            task_type: The plugin type.

        Returns:
            List of matching PluginInstance sorted by priority.
        """
        providers = self.query_by_type(task_type)
        enabled = [p for p in providers if p.enabled]
        enabled.sort(key=lambda p: (p.priority, p.manifest.name))
        return enabled

    def get_fallback_chain(self, task_type: PluginType) -> list[PluginInstance]:
        """Get the fallback chain for a task type.

        Returns all enabled providers for the task type in priority order,
        so the caller can try each one in sequence.

        Args:
            task_type: The plugin type.

        Returns:
            List of providers sorted by priority (primary first).
        """
        return self.get_providers_for_task(task_type)

    # ─── Health Status ─────────────────────────────────────

    def get_health_status(self, plugin_id: str) -> str:
        """Get the health status of a plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Health status string ('ok', 'error', 'unknown').
        """
        reg = self._registrations.get(plugin_id)
        if reg is None:
            return "unknown"
        return reg.instance.health_status

    def get_error_message(self, plugin_id: str) -> str:
        """Get the error message for a failed plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Error message string, or empty string if no error.
        """
        reg = self._registrations.get(plugin_id)
        if reg is None:
            return ""
        return reg.instance.error_message

    # ─── Statistics ───────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict with counts by type, state, enabled/disabled.
        """
        all_instances = self.list_all()
        stats: dict[str, Any] = {
            "total": len(all_instances),
            "enabled": 0,
            "disabled": 0,
            "by_type": {},
            "by_state": {},
            "by_health": {"ok": 0, "error": 0, "unknown": 0},
        }

        for instance in all_instances:
            if instance.enabled:
                stats["enabled"] += 1
            else:
                stats["disabled"] += 1

            plugin_type = instance.manifest.plugin_type.value
            stats["by_type"][plugin_type] = stats["by_type"].get(plugin_type, 0) + 1

            state = instance.state.value
            stats["by_state"][state] = stats["by_state"].get(state, 0) + 1

            health = instance.health_status
            if health in stats["by_health"]:
                stats["by_health"][health] += 1
            else:
                stats["by_health"]["unknown"] = stats["by_health"].get("unknown", 0) + 1

        return stats

    def get_dependency_graph(self) -> DependencyGraph:
        """Get the dependency graph of all registered plugins.

        Returns:
            DependencyGraph with nodes and edges.
        """
        graph = DependencyGraph()
        for reg in self._registrations.values():
            manifest = reg.instance.manifest
            graph.nodes[manifest.id] = {dep.package for dep in manifest.dependencies}
            for dep in manifest.dependencies:
                if dep.package not in graph.edges:
                    graph.edges[dep.package] = set()
                graph.edges[dep.package].add(manifest.id)
        return graph

    # ─── Maintenance ───────────────────────────────────────

    def clear(self) -> None:
        """Clear all registrations."""
        self._registrations.clear()

    def exists(self, plugin_id: str) -> bool:
        """Check if a plugin ID is registered.

        Args:
            plugin_id: The plugin ID.

        Returns:
            True if registered.
        """
        return plugin_id in self._registrations

    def count(self) -> int:
        """Get the total number of registered plugins.

        Returns:
            Plugin count.
        """
        return len(self._registrations)

    # ─── Private ────────────────────────────────────────────────

    def _check_exists(self, plugin_id: str) -> None:
        """Check if a plugin is registered, raise PluginNotFoundError if not."""
        if plugin_id not in self._registrations:
            raise PluginNotFoundError(plugin_id)
