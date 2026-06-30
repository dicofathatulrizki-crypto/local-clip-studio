"""PluginManager — top-level orchestrator for the entire plugin system.

Composes all plugin services into a single API:
- Discovery → Validation → Loading → Registry → Lifecycle → Health
- Plugin scanning and initialization
- Plugin configuration and management
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.cache import PluginCache
from backend.infrastructure.plugins.discovery import PluginDiscovery
from backend.infrastructure.plugins.errors import (
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    translate_plugin_error,
)
from backend.infrastructure.plugins.health import PluginHealthChecker
from backend.infrastructure.plugins.lifecycle import PluginLifecycleManager
from backend.infrastructure.plugins.loader import PluginLoader
from backend.infrastructure.plugins.registry import PluginRegistry
from backend.infrastructure.plugins.resolver import PluginCompatibilityChecker, PluginVersionResolver
from backend.infrastructure.plugins.sandbox import PluginSandbox
from backend.infrastructure.plugins.types import (
    DependencyGraph,
    PluginInfo,
    PluginInstance,
    PluginManifest,
    PluginState,
    PluginType,
)
from backend.infrastructure.plugins.validator import PluginValidator

logger = get_logger(__name__)


class PluginManager:
    """Central orchestrator for the plugin infrastructure.

    Composes all plugin services into a single management API.
    Application code should use this class for all plugin operations.

    Usage:
        manager = PluginManager()
        await manager.initialize()
        stats = manager.registry.get_statistics()
        provider = manager.get_best_provider(PluginType.STT)
    """

    def __init__(
        self,
        discovery: PluginDiscovery | None = None,
        validator: PluginValidator | None = None,
        resolver: PluginCompatibilityChecker | None = None,
        loader: PluginLoader | None = None,
        lifecycle: PluginLifecycleManager | None = None,
        registry: PluginRegistry | None = None,
        sandbox: PluginSandbox | None = None,
        cache: PluginCache | None = None,
        health_checker: PluginHealthChecker | None = None,
        app_version: str = "1.0.0",
        enable_hot_reload: bool = False,
    ) -> None:
        self._cache = cache or PluginCache()
        self._discovery = discovery or PluginDiscovery()
        self._validator = validator or PluginValidator()
        self._resolver = resolver or PluginCompatibilityChecker(app_version=app_version)
        self._loader = loader or PluginLoader(cache=self._cache, enable_hot_reload=enable_hot_reload)
        self._lifecycle = lifecycle or PluginLifecycleManager()
        self._sandbox = sandbox or PluginSandbox()
        self._health = health_checker or PluginHealthChecker()
        self._app_version = app_version
        self._enable_hot_reload = enable_hot_reload
        self._initialized = False

        # Create registry with lifecycle
        self._registry = registry or PluginRegistry(lifecycle_manager=self._lifecycle)

    @property
    def registry(self) -> PluginRegistry:
        """Get the plugin registry."""
        return self._registry

    @property
    def discovery(self) -> PluginDiscovery:
        """Get the plugin discovery service."""
        return self._discovery

    @property
    def sandbox(self) -> PluginSandbox:
        """Get the plugin sandbox."""
        return self._sandbox

    @property
    def health(self) -> PluginHealthChecker:
        """Get the plugin health checker."""
        return self._health

    @property
    def is_initialized(self) -> bool:
        """Check if the plugin manager is initialized."""
        return self._initialized

    # ─── Initialization ─────────────────────────────────────

    async def initialize(
        self,
        builtin_dirs: list[str | Path] | None = None,
        external_dirs: list[str | Path] | None = None,
        allowed_dirs: list[str | Path] | None = None,
        eager_load: bool = True,
    ) -> None:
        """Initialize the plugin system.

        Performs the full plugin lifecycle:
        1. Discover plugins from directories
        2. Validate manifests and compatibility
        3. Load plugins
        4. Initialize and activate
        5. Start health checks

        Args:
            builtin_dirs: Built-in plugin directories.
            external_dirs: External plugin directories.
            allowed_dirs: Allowed filesystem directories.
            eager_load: If True, load all plugins immediately.
        """
        logger.info("Initializing plugin system")

        # Set search directories
        if builtin_dirs:
            self._discovery.set_directories(builtin_dirs, external_dirs or [])

        # Set sandbox directories
        if allowed_dirs:
            self._sandbox.set_allowed_directories(allowed_dirs)

        # Step 1: Discover
        manifests = self._discovery.discover_all()
        logger.info("Plugin discovery complete", extra={"count": len(manifests)})

        # Step 2: Validate and register
        await self._process_manifests(manifests)

        # Step 3: Eager load if requested
        if eager_load:
            await self._load_and_activate_all()

        # Step 4: Start periodic health checks
        active = self._registry.list_by_state(PluginState.ACTIVE)
        if active:
            await self._health.start_periodic_checks(active)

        self._initialized = True
        stats = self._registry.get_statistics()
        logger.info("Plugin system initialized", extra=stats)

    async def _process_manifests(self, manifests: list[PluginManifest]) -> None:
        """Process discovered manifests: validate, check compatibility, register."""
        available: dict[str, PluginManifest] = {m.id: m for m in manifests}

        for manifest in manifests:
            # Validate manifest
            validation_errors = self._validator.validate_manifest(manifest)
            if validation_errors:
                logger.warning(
                    "Plugin manifest validation failed",
                    extra={"plugin_id": manifest.id, "errors": validation_errors},
                )
                continue

            # Check compatibility
            compat_issues = self._resolver.check_plugin_compatibility(manifest)
            if compat_issues:
                logger.warning(
                    "Plugin compatibility check failed",
                    extra={"plugin_id": manifest.id, "issues": compat_issues},
                )
                continue

            # Check dependencies
            dep_issues = self._resolver.check_dependency_compatibility(manifest, available)
            if dep_issues:
                logger.warning(
                    "Plugin dependency check failed",
                    extra={"plugin_id": manifest.id, "issues": dep_issues},
                )
                continue

            # Create plugin instance and register
            instance = PluginInstance(
                manifest=manifest,
                state=PluginState.DISCOVERED,
                source_path=manifest.raw.get("_source_path", ""),
            )
            self._registry.register(instance)

            # Grant permissions
            self._sandbox.grant_permissions(manifest.id, manifest.permissions)

    async def _load_and_activate_all(self) -> None:
        """Load, initialize, and activate all registered plugins."""
        for instance in self._registry.list_all():
            try:
                await self._load_and_activate_instance(instance)
            except PluginError as exc:
                logger.error(
                    "Failed to load plugin",
                    extra={"plugin_id": instance.manifest.id, "error": str(exc)},
                )

    async def _load_and_activate_instance(self, instance: PluginInstance) -> None:
        """Load, initialize, and activate a single plugin instance."""
        # Load
        loaded_instance = self._loader.load(instance.manifest)
        instance.instance = loaded_instance
        instance.state = PluginState.LOADED

        # Initialize
        await self._lifecycle.initialize(instance)

        # Activate
        await self._lifecycle.activate(instance)

    # ─── Plugin Management ──────────────────────────────────

    async def load_plugin(self, manifest: PluginManifest) -> PluginInstance:
        """Load and register a single plugin from a manifest.

        Args:
            manifest: Plugin manifest.

        Returns:
            The loaded PluginInstance.

        Raises:
            PluginLoadError: If loading fails.
        """
        instance = PluginInstance(
            manifest=manifest,
            state=PluginState.DISCOVERED,
        )
        self._registry.register(instance)
        self._sandbox.grant_permissions(manifest.id, manifest.permissions)

        await self._load_and_activate_instance(instance)
        return instance

    async def unload_plugin(self, plugin_id: str) -> None:
        """Unload and unregister a plugin.

        Args:
            plugin_id: The plugin ID.

        Raises:
            PluginNotFoundError: If not found.
        """
        instance = self._registry.get(plugin_id)
        await self._lifecycle.shutdown(instance)
        self._loader.unload(instance)
        self._registry.unregister(plugin_id)
        self._sandbox.revoke_permissions(plugin_id)

    async def reload_plugin(self, plugin_id: str) -> PluginInstance:
        """Reload a plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            The reloaded PluginInstance.
        """
        instance = self._registry.get(plugin_id)
        manifest = instance.manifest
        await self._loader.reload(instance, manifest)
        await self._lifecycle.initialize(instance)
        await self._lifecycle.activate(instance)
        return instance

    async def enable_plugin(self, plugin_id: str) -> None:
        """Enable a plugin and activate it.

        Args:
            plugin_id: The plugin ID.
        """
        self._registry.enable(plugin_id)
        instance = self._registry.get(plugin_id)
        if instance.state == PluginState.DISCOVERED:
            await self._load_and_activate_instance(instance)
        elif instance.state == PluginState.SHUTDOWN:
            await self._load_and_activate_instance(instance)

    async def disable_plugin(self, plugin_id: str) -> None:
        """Disable and deactivate a plugin.

        Args:
            plugin_id: The plugin ID.
        """
        instance = self._registry.get(plugin_id)
        await self._lifecycle.deactivate(instance)
        self._registry.disable(plugin_id)

    # ─── Provider Routing ──────────────────────────────────

    def get_best_provider(
        self,
        task_type: PluginType,
        require_capability: str | None = None,
    ) -> PluginInstance:
        """Get the best available provider for a task type.

        Args:
            task_type: The task type (STT, LLM, etc.).
            require_capability: Optional required capability.

        Returns:
            The best matching PluginInstance.
        """
        return self._registry.get_best_provider(task_type, require_capability)

    def get_providers_for_task(self, task_type: PluginType) -> list[PluginInstance]:
        """Get all providers for a task type.

        Args:
            task_type: The plugin type.

        Returns:
            List of providers sorted by priority.
        """
        return self._registry.get_providers_for_task(task_type)

    def get_fallback_chain(self, task_type: PluginType) -> list[PluginInstance]:
        """Get the fallback chain for a task type.

        Args:
            task_type: The plugin type.

        Returns:
            List of providers in fallback order.
        """
        return self._registry.get_fallback_chain(task_type)

    # ─── Queries ───────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> PluginInstance:
        """Get a plugin instance by ID.

        Args:
            plugin_id: The plugin ID.

        Returns:
            PluginInstance.
        """
        return self._registry.get(plugin_id)

    def get_plugin_info(self, plugin_id: str) -> PluginInfo:
        """Get public plugin info.

        Args:
            plugin_id: The plugin ID.

        Returns:
            PluginInfo.
        """
        return self._registry.get_info(plugin_id)

    def list_plugins(self) -> list[PluginInfo]:
        """List all registered plugins as public info.

        Returns:
            List of PluginInfo.
        """
        return [self._registry.get_info(p.manifest.id) for p in self._registry.list_all()]

    def list_by_type(self, plugin_type: PluginType) -> list[PluginInfo]:
        """List plugins by type.

        Args:
            plugin_type: The plugin type.

        Returns:
            List of PluginInfo.
        """
        return [
            self._registry.get_info(p.manifest.id)
            for p in self._registry.query_by_type(plugin_type)
        ]

    def list_by_capability(self, capability: str) -> list[PluginInfo]:
        """List plugins by capability.

        Args:
            capability: The capability string.

        Returns:
            List of PluginInfo.
        """
        return [
            self._registry.get_info(p.manifest.id)
            for p in self._registry.query_by_capability(capability)
        ]

    # ─── Health ────────────────────────────────────────────

    async def check_plugin_health(self, plugin_id: str) -> dict[str, Any]:
        """Check the health of a specific plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Health result dict.
        """
        instance = self._registry.get(plugin_id)
        return await self._health.check(instance)

    async def check_all_health(self) -> dict[str, dict[str, Any]]:
        """Check the health of all active plugins.

        Returns:
            Dict of plugin_id -> health result.
        """
        active = self._registry.list_by_state(PluginState.ACTIVE)
        return await self._health.check_all(active)

    # ─── Shutdown ──────────────────────────────────────────

    async def shutdown(self) -> None:
        """Shut down the entire plugin system gracefully."""
        logger.info("Shutting down plugin system")

        # Stop health checks
        await self._health.stop_periodic_checks()

        # Shut down all plugins
        all_plugins = self._registry.list_all()
        await self._lifecycle.shutdown_all(all_plugins)

        # Clear state
        self._cache.clear()
        self._registry.clear()
        self._initialized = False

        logger.info("Plugin system shut down")

    # ─── Statistics ────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """Get plugin system statistics.

        Returns:
            Dict with plugin counts and status.
        """
        return self._registry.get_statistics()

    def get_dependency_graph(self) -> DependencyGraph:
        """Get the dependency graph.

        Returns:
            DependencyGraph.
        """
        return self._registry.get_dependency_graph()
