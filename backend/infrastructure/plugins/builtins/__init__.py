"""Built-in Plugins — shipped with the application.

This package contains stub placeholders for built-in plugin
implementations. Each built-in plugin has a manifest.json and
a corresponding Python module.

Built-in plugins are automatically discovered by PluginDiscovery
when the builtin plugin directory is configured.

To add a new built-in plugin:
    1. Create a subdirectory: backend/infrastructure/plugins/builtins/<name>/
    2. Add manifest.json with plugin metadata
    3. Add the plugin implementation module
    4. Register in the application setup
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "manifest.json"


def get_builtin_manifest_dirs() -> list[Path]:
    """Get all built-in plugin manifest directories.

    Scans the builtins package directory for subdirectories
    containing a manifest.json file.

    Returns:
        List of Paths to built-in plugin directories.
    """
    builtins_dir = Path(__file__).parent
    manifest_dirs: list[Path] = []

    if not builtins_dir.exists():
        return manifest_dirs

    for item in sorted(builtins_dir.iterdir()):
        if item.is_dir():
            manifest_file = item / MANIFEST_FILENAME
            if manifest_file.exists():
                manifest_dirs.append(item)

    return manifest_dirs


def get_builtin_manifests() -> list[dict[str, Any]]:
    """Get all built-in plugin manifest dictionaries.

    Returns:
        List of parsed manifest dicts.
    """
    manifests: list[dict[str, Any]] = []
    for plugin_dir in get_builtin_manifest_dirs():
        manifest_path = plugin_dir / MANIFEST_FILENAME
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["_source_path"] = str(plugin_dir)
            manifests.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return manifests


__all__ = [
    "get_builtin_manifest_dirs",
    "get_builtin_manifests",
]
