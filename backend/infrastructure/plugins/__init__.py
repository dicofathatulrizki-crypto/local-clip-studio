"""Plugin Infrastructure — single source of truth for all plugin operations.

This module is the sole entry point for discovering, validating, loading,
registering, activating, deactivating, versioning, and managing every
AI plugin in the system. No other module may load plugins directly.

Usage:
    from backend.infrastructure.plugins import PluginManager

    manager = PluginManager(app_version="1.0.0")
    await manager.initialize(
        builtin_dirs=["backend/infrastructure/plugins/builtins"],
        external_dirs=["~/.localclip/plugins"],
        allowed_dirs=["~/.localclip/projects", "~/.localclip/models"],
    )

    provider = manager.get_best_provider(PluginType.STT)
    result = await provider.transcribe("audio.wav")
"""

from __future__ import annotations

from backend.infrastructure.plugins.cache import PluginCache
from backend.infrastructure.plugins.discovery import PluginDiscovery
from backend.infrastructure.plugins.errors import (
    PluginCapabilityError,
    PluginDependencyError,
    PluginDuplicateError,
    PluginError,
    PluginIntegrityError,
    PluginLoadError,
    PluginManifestError,
    PluginNotFoundError,
    PluginPermissionError,
    PluginRuntimeError,
    PluginVersionError,
    translate_plugin_error,
)
from backend.infrastructure.plugins.health import PluginHealthChecker

# ─── Provider Interfaces ──────────────────────────────────
# Imported for convenience — users can access them here or
# import directly from the interfaces sub-package.
from backend.infrastructure.plugins.interfaces import (
    CaptionProvider,
    ExportProvider,
    LLMProvider,
    STTProvider,
    TranslationProvider,
    VisionProvider,
)
from backend.infrastructure.plugins.lifecycle import PluginLifecycleManager
from backend.infrastructure.plugins.loader import PluginLoader
from backend.infrastructure.plugins.manager import PluginManager
from backend.infrastructure.plugins.registry import PluginRegistry
from backend.infrastructure.plugins.resolver import (
    PluginCompatibilityChecker,
    PluginVersionResolver,
)
from backend.infrastructure.plugins.sandbox import PluginSandbox
from backend.infrastructure.plugins.types import (
    DependencyGraph,
    Permission,
    PluginInfo,
    PluginInstance,
    PluginManifest,
    PluginState,
    PluginType,
)
from backend.infrastructure.plugins.validator import PluginValidator

__all__ = [
    # Manager
    "PluginManager",
    "PluginRegistry",
    "PluginDiscovery",
    "PluginLoader",
    "PluginLifecycleManager",
    "PluginHealthChecker",
    "PluginSandbox",
    "PluginValidator",
    "PluginCache",
    "PluginVersionResolver",
    "PluginCompatibilityChecker",
    # Types
    "PluginManifest",
    "PluginInstance",
    "PluginInfo",
    "PluginState",
    "PluginType",
    "Permission",
    "DependencyGraph",
    # Errors
    "PluginError",
    "PluginLoadError",
    "PluginManifestError",
    "PluginRuntimeError",
    "PluginPermissionError",
    "PluginNotFoundError",
    "PluginDependencyError",
    "PluginVersionError",
    "PluginDuplicateError",
    "PluginCapabilityError",
    "PluginIntegrityError",
    "translate_plugin_error",
    # Provider Interfaces
    "STTProvider",
    "VisionProvider",
    "LLMProvider",
    "CaptionProvider",
    "TranslationProvider",
    "ExportProvider",
]
