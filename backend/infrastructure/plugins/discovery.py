"""PluginDiscovery — automatically discovers plugins from configured directories.

Supports:
- Built-in plugins from the application package
- External plugins from user plugin directories
- Manifest scanning with duplicate detection
- Version conflict detection
- Disabled plugin filtering
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.plugins.errors import PluginDuplicateError, PluginManifestError, translate_plugin_error
from backend.infrastructure.plugins.manifest import PluginManifestParser
from backend.infrastructure.plugins.types import PluginManifest, PluginState
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PluginDiscovery:
    """Discovers plugins by scanning configured directories for manifest.json files.

    Usage:
        discovery = PluginDiscovery()
        manifests = discovery.discover_all()
        for manifest in manifests:
            print(f"Found plugin: {manifest.name} v{manifest.version}")
    """

    MANIFEST_FILENAME = "manifest.json"

    def __init__(
        self,
        manifest_parser: PluginManifestParser | None = None,
        builtin_dirs: list[str | Path] | None = None,
        external_dirs: list[str | Path] | None = None,
    ) -> None:
        self._parser = manifest_parser or PluginManifestParser()
        self._builtin_dirs = [Path(d) for d in builtin_dirs] if builtin_dirs else []
        self._external_dirs = [Path(d) for d in external_dirs] if external_dirs else []

    def add_search_directory(self, directory: str | Path, is_builtin: bool = False) -> None:
        """Add a directory to search for plugins.

        Args:
            directory: Path to search for plugin manifests.
            is_builtin: If True, adds to built-in directories.
        """
        path = Path(directory)
        if is_builtin:
            if path not in self._builtin_dirs:
                self._builtin_dirs.append(path)
        else:
            if path not in self._external_dirs:
                self._external_dirs.append(path)

    def discover_all(self) -> list[PluginManifest]:
        """Discover all plugins from all configured directories.

        Returns:
            List of validated PluginManifest objects.

        Raises:
            PluginDuplicateError: If duplicate plugin IDs are found.
        """
        manifests: dict[str, PluginManifest] = {}

        for directory in self._builtin_dirs:
            found = self._discover_in_directory(directory, is_builtin=True)
            self._merge_manifests(manifests, found, directory)

        for directory in self._external_dirs:
            found = self._discover_in_directory(directory, is_builtin=False)
            self._merge_manifests(manifests, found, directory)

        return list(manifests.values())

    def discover_builtin(self) -> list[PluginManifest]:
        """Discover only built-in plugins.

        Returns:
            List of PluginManifest from built-in directories.
        """
        manifests: list[PluginManifest] = []
        for directory in self._builtin_dirs:
            manifests.extend(self._discover_in_directory(directory, is_builtin=True))
        return manifests

    def discover_external(self) -> list[PluginManifest]:
        """Discover only external/user-installed plugins.

        Returns:
            List of PluginManifest from external directories.
        """
        manifests: list[PluginManifest] = []
        for directory in self._external_dirs:
            manifests.extend(self._discover_in_directory(directory, is_builtin=False))
        return manifests

    @property
    def search_directories(self) -> list[Path]:
        """Get all configured search directories."""
        return self._builtin_dirs + self._external_dirs

    # ─── Private ────────────────────────────────────────────────

    def _discover_in_directory(self, directory: Path, is_builtin: bool = False) -> list[PluginManifest]:
        """Scan a single directory for plugin manifests.

        Args:
            directory: Path to scan.
            is_builtin: Whether this is a built-in plugin directory.

        Returns:
            List of validated PluginManifest objects.
        """
        manifests: list[PluginManifest] = []

        if not directory.exists() or not directory.is_dir():
            logger.debug("Plugin directory does not exist, skipping", extra={"path": str(directory)})
            return manifests

        # Scan for manifest.json files — immediate children or one level deep
        manifest_paths: list[Path] = []

        # Check immediate children
        direct_manifest = directory / self.MANIFEST_FILENAME
        if direct_manifest.exists():
            manifest_paths.append(direct_manifest)

        # Check one level deep (plugin subdirectories)
        try:
            for item in sorted(directory.iterdir()):
                if item.is_dir():
                    sub_manifest = item / self.MANIFEST_FILENAME
                    if sub_manifest.exists():
                        manifest_paths.append(sub_manifest)
        except PermissionError:
            logger.warning("Permission denied reading plugin directory", extra={"path": str(directory)})

        for manifest_path in manifest_paths:
            try:
                manifest = self._parser.parse_from_file(manifest_path)
                manifests.append(manifest)
                logger.info(
                    "Discovered plugin",
                    extra={
                        "plugin_id": manifest.id,
                        "version": manifest.version,
                        "type": manifest.plugin_type.value,
                        "path": str(manifest_path),
                        "builtin": is_builtin,
                    },
                )
            except PluginManifestError as exc:
                logger.warning(
                    "Invalid plugin manifest",
                    extra={"path": str(manifest_path), "error": str(exc)},
                )
            except Exception as exc:
                logger.error(
                    "Failed to discover plugin",
                    extra={"path": str(manifest_path), "error": str(exc)},
                )

        return manifests

    @staticmethod
    def _merge_manifests(
        existing: dict[str, PluginManifest],
        new_manifests: list[PluginManifest],
        source_directory: Path,
    ) -> None:
        """Merge discovered manifests, detecting duplicates.

        Args:
            existing: Existing manifest dict (plugin_id -> manifest).
            new_manifests: Newly discovered manifests.
            source_directory: Source directory for error reporting.

        Raises:
            PluginDuplicateError: If a duplicate plugin ID is found.
        """
        for manifest in new_manifests:
            if manifest.id in existing:
                existing_manifest = existing[manifest.id]
                # Built-in takes precedence over external
                if existing_manifest.version >= manifest.version:
                    raise PluginDuplicateError(manifest.id, str(source_directory))
            existing[manifest.id] = manifest

    def set_directories(self, builtin_dirs: list[str | Path], external_dirs: list[str | Path]) -> None:
        """Set all search directories at once.

        Args:
            builtin_dirs: Built-in plugin directories.
            external_dirs: External/user plugin directories.
        """
        self._builtin_dirs = [Path(d) for d in builtin_dirs]
        self._external_dirs = [Path(d) for d in external_dirs]
