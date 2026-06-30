"""PluginErrorTranslator — structured error handling for the plugin system.

All plugin errors map to structured exceptions with error codes,
messages, and recovery hints. Raw exceptions from plugin code are
never exposed to callers.
"""
from __future__ import annotations


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    def __init__(
        self,
        message: str,
        plugin_id: str = "",
        error_code: str = "ERR-PLUG-000",
        recovery_hint: str = "",
    ) -> None:
        self.plugin_id = plugin_id
        self.error_code = error_code
        self.recovery_hint = recovery_hint
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.__class__.__name__,
            "code": self.error_code,
            "message": str(self),
            "plugin_id": self.plugin_id,
            "recovery_hint": self.recovery_hint,
        }


class PluginLoadError(PluginError):
    """Plugin failed to load (import error, missing entry point)."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-001", "Check plugin compatibility and dependencies")


class PluginManifestError(PluginError):
    """Plugin manifest is invalid or missing required fields."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-002", "Plugin developer must fix manifest.json")


class PluginRuntimeError(PluginError):
    """Plugin crashed or raised an unhandled exception at runtime."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-003", "Plugin disabled; report issue to plugin author")


class PluginPermissionError(PluginError):
    """Plugin requested a permission that was denied."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-004", "Review plugin permissions in settings")


class PluginNotFoundError(PluginError):
    """Plugin not found in the registry."""

    def __init__(self, plugin_id: str) -> None:
        super().__init__(
            f"Plugin '{plugin_id}' not found",
            plugin_id,
            "ERR-PLUG-005",
            "Verify the plugin is installed and enabled",
        )


class PluginDependencyError(PluginError):
    """Plugin has missing or incompatible dependencies."""

    def __init__(self, message: str, plugin_id: str = "", dependency: str = "") -> None:
        self.dependency = dependency
        super().__init__(message, plugin_id, "ERR-PLUG-006", "Install missing dependencies")


class PluginVersionError(PluginError):
    """Plugin version is incompatible with the application."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-007", "Update the plugin or application")


class PluginDuplicateError(PluginError):
    """Duplicate plugin detected."""

    def __init__(self, plugin_id: str, existing_path: str) -> None:
        super().__init__(
            f"Duplicate plugin '{plugin_id}' found at {existing_path}",
            plugin_id,
            "ERR-PLUG-008",
            "Remove the duplicate plugin",
        )


class PluginCapabilityError(PluginError):
    """Plugin does not support the requested capability."""

    def __init__(self, plugin_id: str, capability: str) -> None:
        self.capability = capability
        super().__init__(
            f"Plugin '{plugin_id}' does not support capability '{capability}'",
            plugin_id,
            "ERR-PLUG-009",
            "Choose a different plugin that supports this capability",
        )


class PluginIntegrityError(PluginError):
    """Plugin checksum or signature validation failed."""

    def __init__(self, message: str, plugin_id: str = "") -> None:
        super().__init__(message, plugin_id, "ERR-PLUG-010", "Reinstall the plugin or contact the author")


def translate_plugin_error(exc: Exception, plugin_id: str = "") -> PluginError:
    """Translate an arbitrary exception into a PluginError.

    Args:
        exc: The original exception.
        plugin_id: Optional plugin ID for context.

    Returns:
        An appropriate PluginError subclass.
    """
    if isinstance(exc, PluginError):
        return exc
    if isinstance(exc, ImportError):
        return PluginLoadError(str(exc), plugin_id)
    if isinstance(exc, ModuleNotFoundError):
        return PluginLoadError(f"Module not found: {exc}", plugin_id)
    if isinstance(exc, PermissionError):
        return PluginPermissionError(str(exc), plugin_id)
    if isinstance(exc, ValueError):
        return PluginManifestError(str(exc), plugin_id)
    return PluginRuntimeError(str(exc), plugin_id)
