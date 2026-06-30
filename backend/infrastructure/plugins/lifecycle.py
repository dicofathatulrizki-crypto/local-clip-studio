"""PluginLifecycleManager — manages plugin lifecycle transitions.

Handles:
- Lifecycle hooks (pre_init, post_init, pre_activate, post_activate, etc.)
- State transitions: DISCOVERED → LOADED → INITIALIZED → ACTIVE → SHUTDOWN
- Graceful shutdown with timeout
- Lifecycle event logging
"""
from __future__ import annotations

import asyncio

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.errors import translate_plugin_error
from backend.infrastructure.plugins.types import PluginInstance, PluginState

logger = get_logger(__name__)


class PluginLifecycleManager:
    """Manages the lifecycle of plugin instances.

    Standard lifecycle:
        DISCOVERED → LOADED → INITIALIZED → ACTIVE → SHUTDOWN

    Usage:
        manager = PluginLifecycleManager()
        await manager.initialize(instance)
        await manager.activate(instance)
        await manager.shutdown(instance)
    """

    SHUTDOWN_TIMEOUT = 10  # seconds

    def __init__(self, shutdown_timeout: int = SHUTDOWN_TIMEOUT) -> None:
        self._timeout = shutdown_timeout

    async def initialize(self, instance: PluginInstance) -> None:
        """Initialize a loaded plugin.

        Calls the init() method on the plugin if it exists.
        Transitions state from LOADED to INITIALIZED.

        Args:
            instance: The plugin instance to initialize.

        Raises:
            PluginRuntimeError: If initialization fails.
        """
        if instance.state != PluginState.LOADED:
            logger.warning(
                "Cannot initialize plugin: not in LOADED state",
                extra={"plugin_id": instance.manifest.id, "state": instance.state.value},
            )
            return

        plugin = instance.instance
        if plugin is None:
            instance.state = PluginState.ERROR
            instance.error_message = "Plugin instance is None"
            return

        try:
            if hasattr(plugin, "init"):
                result = plugin.init()
                if hasattr(result, "__await__"):
                    await result

            instance.state = PluginState.INITIALIZED
            logger.info("Plugin initialized", extra={"plugin_id": instance.manifest.id})

        except Exception as exc:
            instance.state = PluginState.ERROR
            instance.error_message = str(exc)
            error = translate_plugin_error(exc, instance.manifest.id)
            logger.error(
                "Plugin initialization failed",
                extra={"plugin_id": instance.manifest.id, "error": str(exc)},
            )
            raise error from exc

    async def activate(self, instance: PluginInstance) -> None:
        """Activate an initialized plugin.

        Transitions state from INITIALIZED to ACTIVE.

        Args:
            instance: The plugin instance to activate.

        Raises:
            PluginRuntimeError: If activation fails.
        """
        if instance.state not in (PluginState.INITIALIZED, PluginState.LOADED):
            logger.warning(
                "Cannot activate plugin: not in INITIALIZED or LOADED state",
                extra={"plugin_id": instance.manifest.id, "state": instance.state.value},
            )
            return

        plugin = instance.instance
        if plugin is None:
            instance.state = PluginState.ERROR
            instance.error_message = "Plugin instance is None"
            return

        try:
            if hasattr(plugin, "activate"):
                result = plugin.activate()
                if hasattr(result, "__await__"):
                    await result

            instance.state = PluginState.ACTIVE
            logger.info("Plugin activated", extra={"plugin_id": instance.manifest.id})

        except Exception as exc:
            instance.state = PluginState.ERROR
            instance.error_message = str(exc)
            error = translate_plugin_error(exc, instance.manifest.id)
            logger.error(
                "Plugin activation failed",
                extra={"plugin_id": instance.manifest.id, "error": str(exc)},
            )
            raise error from exc

    async def deactivate(self, instance: PluginInstance) -> None:
        """Deactivate an active plugin.

        Transitions state from ACTIVE to INITIALIZED.

        Args:
            instance: The plugin instance to deactivate.
        """
        if instance.state != PluginState.ACTIVE:
            logger.warning(
                "Cannot deactivate plugin: not in ACTIVE state",
                extra={"plugin_id": instance.manifest.id, "state": instance.state.value},
            )
            return

        plugin = instance.instance
        try:
            if plugin is not None and hasattr(plugin, "deactivate"):
                result = plugin.deactivate()
                if hasattr(result, "__await__"):
                    await result

            instance.state = PluginState.INITIALIZED
            logger.info("Plugin deactivated", extra={"plugin_id": instance.manifest.id})

        except Exception as exc:
            logger.warning(
                "Plugin deactivation failed",
                extra={"plugin_id": instance.manifest.id, "error": str(exc)},
            )

    async def shutdown(self, instance: PluginInstance) -> None:
        """Gracefully shut down a plugin.

        Calls shutdown() on the plugin with a timeout.
        Transitions to SHUTDOWN state regardless of outcome.

        Args:
            instance: The plugin instance to shut down.
        """
        plugin = instance.instance
        if plugin is not None:
            try:
                if hasattr(plugin, "shutdown"):
                    result = plugin.shutdown()
                    if hasattr(result, "__await__"):
                        await asyncio.wait_for(result, timeout=self._timeout)

                logger.info("Plugin shut down", extra={"plugin_id": instance.manifest.id})

            except TimeoutError:
                logger.warning(
                    "Plugin shutdown timed out",
                    extra={"plugin_id": instance.manifest.id, "timeout": self._timeout},
                )
            except Exception as exc:
                logger.warning(
                    "Plugin shutdown error",
                    extra={"plugin_id": instance.manifest.id, "error": str(exc)},
                )

        instance.state = PluginState.SHUTDOWN
        instance.instance = None

    async def shutdown_all(self, instances: list[PluginInstance]) -> None:
        """Shut down all plugins gracefully.

        Args:
            instances: List of plugin instances to shut down.
        """
        logger.info("Shutting down all plugins", extra={"count": len(instances)})
        for instance in instances:
            await self.shutdown(instance)

    def get_state(self, instance: PluginInstance) -> PluginState:
        """Get the current lifecycle state of a plugin.

        Args:
            instance: The plugin instance.

        Returns:
            Current PluginState.
        """
        return instance.state

    def is_active(self, instance: PluginInstance) -> bool:
        """Check if a plugin is in ACTIVE state.

        Args:
            instance: The plugin instance.

        Returns:
            True if ACTIVE.
        """
        return instance.state == PluginState.ACTIVE

    def is_initialized(self, instance: PluginInstance) -> bool:
        """Check if a plugin is in INITIALIZED or ACTIVE state.

        Args:
            instance: The plugin instance.

        Returns:
            True if INITIALIZED or ACTIVE.
        """
        return instance.state in (PluginState.INITIALIZED, PluginState.ACTIVE)
