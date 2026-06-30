"""Data types for the plugin infrastructure.

Defines the PluginManifest, PluginState, PluginInfo, and all supporting
value objects used throughout the plugin system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginState(Enum):
    """Lifecycle states of a plugin."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    ERROR = "error"
    SHUTDOWN = "shutdown"
    DISABLED = "disabled"


class PluginType(Enum):
    """Plugin category types corresponding to provider interfaces."""
    STT = "stt"
    LLM = "llm"
    VISION = "vision"
    CAPTION = "caption"
    TRANSLATION = "translation"
    EXPORT = "export"
    UNKNOWN = "unknown"


class Permission(Enum):
    """Declarable plugin permissions."""
    GPU = "gpu"
    NETWORK = "network"
    NETWORK_LOCALHOST = "network:localhost"
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"
    MODEL_ACCESS = "model_access"
    AUDIO_CAPTURE = "audio_capture"
    DISPLAY_CAPTURE = "display_capture"


@dataclass
class PluginModelInfo:
    """Model metadata declared in a plugin manifest."""
    id: str = ""
    size_mb: int = 0
    vram_mb: int = 0
    performance: str = ""


@dataclass
class PluginDependency:
    """A dependency declared by a plugin."""
    package: str = ""
    version_spec: str = ""


@dataclass
class PluginManifest:
    """Complete plugin manifest parsed from manifest.json."""
    id: str = ""
    name: str = ""
    version: str = "0.0.0"
    min_app_version: str = "1.0.0"
    max_app_version: str | None = None
    plugin_type: PluginType = PluginType.UNKNOWN
    author: str = ""
    description: str = ""
    entry_point: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: list[Permission] = field(default_factory=list)
    models: list[PluginModelInfo] = field(default_factory=list)
    dependencies: list[PluginDependency] = field(default_factory=list)
    optional_dependencies: list[PluginDependency] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    signature: str | None = None
    homepage: str = ""
    license: str = ""
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def is_compatible_with_app(self, app_version: str) -> bool:
        """Check if this plugin is compatible with the given app version."""
        from packaging.version import Version
        app = Version(app_version)
        if app < Version(self.min_app_version):
            return False
        if self.max_app_version and app > Version(self.max_app_version):
            return False
        return True


@dataclass
class PluginInstance:
    """A loaded plugin instance with its runtime state."""
    manifest: PluginManifest = field(default_factory=PluginManifest)
    instance: Any = None  # The actual plugin object
    state: PluginState = PluginState.DISCOVERED
    source_path: str = ""
    priority: int = 100
    enabled: bool = True
    error_message: str = ""
    loaded_at: float = 0.0
    last_health_check: float = 0.0
    health_status: str = "unknown"
    ref_count: int = 0


@dataclass
class PluginInfo:
    """Public information about a plugin for API responses."""
    id: str = ""
    name: str = ""
    version: str = ""
    plugin_type: str = ""
    author: str = ""
    description: str = ""
    state: str = "discovered"
    enabled: bool = True
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    health_status: str = "unknown"
    error_message: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginRegistration:
    """Internal registration entry tracking a plugin in the registry."""
    instance: PluginInstance = field(default_factory=PluginInstance)
    registered_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class DependencyGraph:
    """Dependency graph for plugin resolution."""
    nodes: dict[str, set[str]] = field(default_factory=dict)  # plugin_id -> set of dependency ids
    edges: dict[str, set[str]] = field(default_factory=dict)  # plugin_id -> set of dependents


@dataclass
class PluginCacheEntry:
    """A cached plugin load result."""
    manifest_path: str = ""
    manifest: PluginManifest | None = None
    instance: Any = None
    cached_at: float = 0.0
    checksum: str = ""
    valid: bool = False
