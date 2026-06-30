"""PluginValidator — validates plugin manifests, interfaces, versions, and dependencies.

Provides validation for:
- Manifest schema completeness
- Interface implementation requirements
- Version compatibility
- Dependency graph validation
- Cyclic dependency detection
- Duplicate plugin ID detection
- Checksum validation
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from backend.infrastructure.plugins.errors import (
    PluginCapabilityError,
    PluginDependencyError,
    PluginDuplicateError,
    PluginIntegrityError,
    PluginManifestError,
    PluginVersionError,
)
from backend.infrastructure.plugins.types import (
    DependencyGraph,
    PluginManifest,
    PluginState,
    PluginType,
)


class PluginValidator:
    """Validates plugin manifests, dependencies, and compatibility.

    Usage:
        validator = PluginValidator()
        errors = validator.validate_manifest(manifest)
        deps_ok = validator.validate_dependencies(manifest, all_manifests)
    """

    # Known provider interface classes for validation
    PROVIDER_INTERFACES: dict[PluginType, str] = {
        PluginType.STT: "STTProvider",
        PluginType.LLM: "LLMProvider",
        PluginType.VISION: "VisionProvider",
        PluginType.CAPTION: "CaptionProvider",
        PluginType.TRANSLATION: "TranslationProvider",
        PluginType.EXPORT: "ExportProvider",
    }

    def validate_manifest(self, manifest: PluginManifest) -> list[str]:
        """Validate a parsed manifest and return error messages.

        Args:
            manifest: The parsed PluginManifest.

        Returns:
            List of error messages (empty if valid).
        """
        errors: list[str] = []

        # Version format
        if not self._is_valid_semver(manifest.version):
            errors.append(f"Invalid version '{manifest.version}': must be semver")

        if not self._is_valid_semver(manifest.min_app_version):
            errors.append(f"Invalid min_app_version '{manifest.min_app_version}': must be semver")

        # Entry point format
        if ":" not in manifest.entry_point:
            errors.append(f"Entry point '{manifest.entry_point}' must be in module:ClassName format")

        # Plugin type
        if manifest.plugin_type == PluginType.UNKNOWN:
            errors.append("Plugin type is unknown or missing")

        # Capabilities
        if not manifest.capabilities:
            errors.append("Plugin must declare at least one capability")

        return errors

    def validate_interface(self, manifest: PluginManifest, plugin_instance: Any) -> list[str]:
        """Validate that a plugin instance implements the required interface methods.

        Args:
            manifest: Plugin manifest defining the expected type.
            plugin_instance: The loaded plugin object.

        Returns:
            List of missing method names (empty if valid).
        """
        required_methods = self._get_required_methods(manifest.plugin_type)
        missing: list[str] = []
        for method in required_methods:
            if not hasattr(plugin_instance, method):
                missing.append(method)
            elif not callable(getattr(plugin_instance, method)):
                missing.append(f"{method} (not callable)")
        return missing

    def validate_version_compatibility(
        self,
        manifest: PluginManifest,
        app_version: str,
    ) -> list[str]:
        """Validate plugin version compatibility with the application.

        Args:
            manifest: Plugin manifest.
            app_version: Current application version (semver).

        Returns:
            List of compatibility errors (empty if compatible).
        """
        errors: list[str] = []
        from packaging.version import Version

        app_ver = Version(app_version)
        min_ver = Version(manifest.min_app_version)

        if app_ver < min_ver:
            errors.append(
                f"App version {app_version} is below minimum required {manifest.min_app_version}"
            )

        if manifest.max_app_version:
            max_ver = Version(manifest.max_app_version)
            if app_ver > max_ver:
                errors.append(
                    f"App version {app_version} exceeds maximum supported {manifest.max_app_version}"
                )

        return errors

    def validate_dependencies(
        self,
        manifest: PluginManifest,
        all_manifests: dict[str, PluginManifest],
    ) -> list[str]:
        """Validate that all dependencies are satisfied.

        Args:
            manifest: The plugin manifest to check.
            all_manifests: All discovered manifests (plugin_id -> manifest).

        Returns:
            List of dependency errors (empty if all satisfied).
        """
        errors: list[str] = []

        for dep in manifest.dependencies:
            if dep.package not in all_manifests:
                errors.append(f"Dependency '{dep.package}' is not installed")
            elif dep.version_spec:
                dep_manifest = all_manifests[dep.package]
                if not self._satisfies_version(dep_manifest.version, dep.version_spec):
                    errors.append(
                        f"Dependency '{dep.package}' version {dep_manifest.version} "
                        f"does not satisfy '{dep.version_spec}'"
                    )

        return errors

    def detect_cyclic_dependencies(
        self,
        plugin_id: str,
        manifest: PluginManifest,
        all_manifests: dict[str, PluginManifest],
        visited: set[str] | None = None,
        path: list[str] | None = None,
    ) -> list[list[str]]:
        """Detect cyclic dependencies starting from a plugin.

        Args:
            plugin_id: The plugin to start from.
            manifest: The plugin's manifest.
            all_manifests: All discovered manifests.
            visited: Set of already visited plugins (internal).
            path: Current dependency path (internal).

        Returns:
            List of cycles found, where each cycle is a list of plugin IDs.
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        cycles: list[list[str]] = []

        if plugin_id in path:
            cycle_start = path.index(plugin_id)
            cycles.append(path[cycle_start:] + [plugin_id])
            return cycles

        if plugin_id in visited:
            return cycles

        visited.add(plugin_id)
        path.append(plugin_id)

        for dep in manifest.dependencies:
            if dep.package in all_manifests:
                dep_manifest = all_manifests[dep.package]
                dep_cycles = self.detect_cyclic_dependencies(
                    dep_manifest.id, dep_manifest, all_manifests,
                    visited, list(path),
                )
                cycles.extend(dep_cycles)

        return cycles

    def validate_checksum(self, manifest: PluginManifest, file_paths: list[str | Path]) -> list[str]:
        """Validate checksums of plugin files against the manifest checksum.

        Args:
            manifest: Plugin manifest with checksum field.
            file_paths: List of plugin file paths to checksum.

        Returns:
            List of integrity errors (empty if checksums match).
        """
        if not manifest.checksum:
            return []  # No checksum to validate

        errors: list[str] = []
        combined = hashlib.sha256()

        for file_path in sorted(str(p) for p in file_paths):
            try:
                with open(file_path, "rb") as f:
                    combined.update(f.read())
            except (FileNotFoundError, PermissionError, OSError) as exc:
                errors.append(f"Cannot read file for checksum: {file_path} ({exc})")

        computed = combined.hexdigest()
        if computed != manifest.checksum:
            errors.append(
                f"Checksum mismatch for {manifest.id}: "
                f"expected {manifest.checksum[:16]}..., got {computed[:16]}..."
            )

        return errors

    def detect_duplicates(
        self,
        manifests: list[PluginManifest],
    ) -> list[tuple[str, str, str]]:
        """Detect duplicate plugin IDs across a list of manifests.

        Args:
            manifests: List of discovered manifests.

        Returns:
            List of (plugin_id, version_1, version_2) tuples for duplicates.
        """
        seen: dict[str, PluginManifest] = {}
        duplicates: list[tuple[str, str, str]] = []

        for manifest in manifests:
            if manifest.id in seen:
                existing = seen[manifest.id]
                duplicates.append((manifest.id, existing.version, manifest.version))
            seen[manifest.id] = manifest

        return duplicates

    def build_dependency_graph(self, manifests: list[PluginManifest]) -> DependencyGraph:
        """Build a dependency graph from a list of manifests.

        Args:
            manifests: List of discovered manifests.

        Returns:
            DependencyGraph with nodes and edges.
        """
        graph = DependencyGraph()

        for manifest in manifests:
            graph.nodes[manifest.id] = {dep.package for dep in manifest.dependencies}
            for dep in manifest.dependencies:
                if dep.package not in graph.edges:
                    graph.edges[dep.package] = set()
                graph.edges[dep.package].add(manifest.id)

        return graph

    def check_capability(self, manifest: PluginManifest, capability: str) -> bool:
        """Check if a plugin supports a specific capability.

        Args:
            manifest: Plugin manifest.
            capability: Capability string to check.

        Returns:
            True if the plugin supports the capability.
        """
        return capability in manifest.capabilities

    # ─── Private ────────────────────────────────────────────────

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if a string is a valid semver version."""
        import re
        return bool(re.match(r"^\d+\.\d+\.\d+", version))

    @staticmethod
    def _satisfies_version(version: str, version_spec: str) -> bool:
        """Check if a version satisfies a version spec.

        Supports: '>=1.0.0', '^1.0.0', '~1.0.0', '1.0.0'.
        """
        from packaging.version import Version, InvalidVersion
        try:
            ver = Version(version)
        except InvalidVersion:
            return False

        spec = version_spec.strip()

        if spec.startswith(">="):
            try:
                return ver >= Version(spec[2:])
            except InvalidVersion:
                return False
        elif spec.startswith("^"):
            try:
                target = Version(spec[1:])
                return ver.major == target.major and ver >= target
            except InvalidVersion:
                return False
        elif spec.startswith("~"):
            try:
                target = Version(spec[1:])
                return (ver.major == target.major and ver.minor == target.minor and ver >= target)
            except InvalidVersion:
                return False
        else:
            try:
                return ver == Version(spec)
            except InvalidVersion:
                return False

    @staticmethod
    def _get_required_methods(plugin_type: PluginType) -> list[str]:
        """Get the set of required methods for a plugin type."""
        methods: dict[PluginType, list[str]] = {
            PluginType.STT: [
                "load", "transcribe", "get_available_models", "unload", "health_check",
            ],
            PluginType.LLM: [
                "load", "generate", "get_available_models", "unload", "health_check",
            ],
            PluginType.VISION: [
                "load", "detect", "detect_batch", "unload", "health_check",
            ],
            PluginType.CAPTION: [
                "load", "generate_captions", "get_styles", "unload", "health_check",
            ],
            PluginType.TRANSLATION: [
                "load", "translate", "get_supported_languages", "unload", "health_check",
            ],
            PluginType.EXPORT: [
                "load", "export", "get_supported_formats", "unload", "health_check",
            ],
        }
        return methods.get(plugin_type, [])
