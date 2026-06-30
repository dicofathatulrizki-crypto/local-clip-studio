"""PluginManifestParser — validates and parses plugin manifest.json files.

Supports full manifest schema including:
- Plugin identity (id, name, version)
- Compatibility (min/max app version)
- Entry point, capabilities, permissions
- Models, dependencies, optional dependencies
- Configuration schema, checksum, signature
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.infrastructure.plugins.errors import PluginManifestError
from backend.infrastructure.plugins.types import (
    Permission,
    PluginDependency,
    PluginManifest,
    PluginModelInfo,
    PluginType,
)

# Required fields that must be present in every manifest
REQUIRED_FIELDS = frozenset({"id", "name", "version", "plugin_type", "entry_point"})

# Allowed manifest schema version
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0", "1"})

# Valid plugin types
VALID_PLUGIN_TYPES = frozenset(PluginType.__members__.values())


class PluginManifestParser:
    """Parses and validates plugin manifest files.

    Usage:
        parser = PluginManifestParser()
        manifest = parser.parse_from_file("/path/to/plugin/manifest.json")
        if manifest:
            print(f"Loaded plugin: {manifest.name} v{manifest.version}")
    """

    MINIMUM_MANIFEST_VERSION = "1.0"

    def parse_from_file(self, manifest_path: str | Path) -> PluginManifest:
        """Parse a manifest.json file and return a validated PluginManifest.

        Args:
            manifest_path: Path to manifest.json.

        Returns:
            A validated PluginManifest instance.

        Raises:
            PluginManifestError: If the manifest is invalid or missing required fields.
            FileNotFoundError: If the manifest file does not exist.
        """
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON in manifest: {exc}"
            raise PluginManifestError(msg) from exc

        return self.parse_from_dict(data, str(manifest_path))

    def parse_from_dict(self, data: dict[str, Any], source: str = "") -> PluginManifest:
        """Parse a manifest dictionary into a validated PluginManifest.

        Args:
            data: Manifest dictionary.
            source: Optional source description (e.g., file path).

        Returns:
            Validated PluginManifest.

        Raises:
            PluginManifestError: If validation fails.
        """
        self._validate_required_fields(data, source)

        manifest = PluginManifest(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            version=self._parse_version(data.get("version", "0.0.0"), source),
            min_app_version=self._parse_version(data.get("min_app_version", "1.0.0"), source),
            max_app_version=self._parse_optional_version(data.get("max_app_version"), source),
            plugin_type=self._parse_plugin_type(data.get("plugin_type", "unknown"), source),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            entry_point=str(data.get("entry_point", "")),
            capabilities=self._parse_list(data, "capabilities"),
            permissions=self._parse_permissions(data.get("permissions", [])),
            models=self._parse_models(data.get("models", [])),
            dependencies=self._parse_dependencies(data.get("dependencies", {})),
            optional_dependencies=self._parse_dependencies(data.get("optional_dependencies", {})),
            config_schema=data.get("config_schema", {}),
            checksum=str(data.get("checksum", "")),
            signature=data.get("signature"),
            homepage=str(data.get("homepage", "")),
            license=str(data.get("license", "")),
            tags=self._parse_list(data, "tags"),
            raw=data,
        )

        # Validate entry point format
        if ":" not in manifest.entry_point:
            msg = f"Entry point must be in 'module:ClassName' format, got '{manifest.entry_point}'"
            raise PluginManifestError(msg, manifest.id)

        return manifest

    def validate_manifest(self, manifest: PluginManifest) -> list[str]:
        """Validate a parsed manifest and return a list of warning messages.

        Args:
            manifest: The parsed PluginManifest to validate.

        Returns:
            List of warning messages (empty if no warnings).
        """
        warnings: list[str] = []

        if not manifest.description:
            warnings.append(f"Plugin '{manifest.id}' has no description")

        if not manifest.author:
            warnings.append(f"Plugin '{manifest.id}' has no author")

        if not manifest.capabilities:
            warnings.append(f"Plugin '{manifest.id}' declares no capabilities")

        if not manifest.checksum:
            warnings.append(f"Plugin '{manifest.id}' has no checksum for integrity verification")

        return warnings

    # ─── Private ────────────────────────────────────────────────

    def _validate_required_fields(self, data: dict[str, Any], source: str) -> None:
        """Validate that all required fields are present."""
        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            fields = ", ".join(sorted(missing))
            loc = f" in {source}" if source else ""
            msg = f"Missing required manifest fields{loc}: {fields}"
            raise PluginManifestError(msg)

        plugin_id = data.get("id", "unknown")
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            msg = f"Plugin id must be a non-empty string{', got: ' + repr(plugin_id) if 'plugin_id' in data else ''}"
            raise PluginManifestError(msg, str(plugin_id))

    @staticmethod
    def _parse_version(version_str: str, source: str = "") -> str:
        """Parse and validate a version string."""
        import re
        if not re.match(r"^\d+\.\d+\.\d+", version_str):
            loc = f" in {source}" if source else ""
            msg = f"Invalid version format{loc}: '{version_str}'. Expected semver (e.g., '1.0.0')"
            raise PluginManifestError(msg)
        return version_str

    @staticmethod
    def _parse_optional_version(version_str: str | None, source: str = "") -> str | None:
        """Parse an optional version string."""
        if version_str is None:
            return None
        import re
        if not re.match(r"^\d+\.\d+\.\d+", version_str):
            loc = f" in {source}" if source else ""
            msg = f"Invalid version format{loc}: '{version_str}'. Expected semver (e.g., '1.0.0')"
            raise PluginManifestError(msg)
        return version_str

    @staticmethod
    def _parse_plugin_type(type_str: str, source: str = "") -> PluginType:
        """Parse plugin type string into PluginType enum."""
        type_map = {
            "stt": PluginType.STT,
            "llm": PluginType.LLM,
            "vision": PluginType.VISION,
            "caption": PluginType.CAPTION,
            "translation": PluginType.TRANSLATION,
            "export": PluginType.EXPORT,
        }
        plugin_type = type_map.get(type_str.lower())
        if plugin_type is None:
            loc = f" in {source}" if source else ""
            msg = f"Unknown plugin type '{type_str}'{loc}. Valid types: {', '.join(type_map.keys())}"
            raise PluginManifestError(msg)
        return plugin_type

    @staticmethod
    def _parse_list(data: dict[str, Any], key: str) -> list[str]:
        """Parse a list field from manifest data."""
        value = data.get(key, [])
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    @staticmethod
    def _parse_permissions(perms: list[Any]) -> list[Permission]:
        """Parse permission strings into Permission enums."""
        result: list[Permission] = []
        perm_map = {p.value: p for p in Permission}
        for item in perms:
            if isinstance(item, str) and item in perm_map:
                result.append(perm_map[item])
        return result

    @staticmethod
    def _parse_models(models: list[dict[str, Any]]) -> list[PluginModelInfo]:
        """Parse model declarations from manifest."""
        result: list[PluginModelInfo] = []
        for model in models:
            if isinstance(model, dict) and "id" in model:
                result.append(PluginModelInfo(
                    id=str(model["id"]),
                    size_mb=int(model.get("size_mb", 0)),
                    vram_mb=int(model.get("vram_mb", 0)),
                    performance=str(model.get("performance", "")),
                ))
        return result

    @staticmethod
    def _parse_dependencies(raw: dict[str, Any]) -> list[PluginDependency]:
        """Parse dependency declarations from manifest.

        Accepts format: {"package_name": "version_spec"}.
        """
        result: list[PluginDependency] = []
        if isinstance(raw, dict):
            for package, version_spec in raw.items():
                if isinstance(package, str):
                    result.append(PluginDependency(
                        package=package,
                        version_spec=str(version_spec) if version_spec else "",
                    ))
        return result
