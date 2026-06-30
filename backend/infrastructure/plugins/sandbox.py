"""PluginSandbox — enforces permissions, sandbox boundaries, and security restrictions.

Plugins never gain unrestricted access to the application. The sandbox:
- Validates requested permissions against granted permissions
- Restricts filesystem access to allowed directories
- Controls network access based on permission flags
- Manages model access permissions
- Validates configuration values against schema
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.errors import PluginPermissionError
from backend.infrastructure.plugins.types import Permission, PluginManifest

logger = get_logger(__name__)


class PluginSandbox:
    """Enforces plugin security boundaries.

    Usage:
        sandbox = PluginSandbox()
        sandbox.check_permission(manifest, Permission.GPU)
        safe_path = sandbox.resolve_path(manifest, user_provided_path)
    """

    def __init__(self, allowed_dirs: list[str | Path] | None = None) -> None:
        self._allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]
        self._granted_permissions: dict[str, set[Permission]] = {}

    def grant_permissions(self, plugin_id: str, permissions: list[Permission]) -> None:
        """Grant specific permissions to a plugin.

        Args:
            plugin_id: The plugin ID.
            permissions: List of permissions to grant.
        """
        self._granted_permissions[plugin_id] = set(permissions)

    def revoke_permissions(self, plugin_id: str) -> None:
        """Revoke all permissions from a plugin.

        Args:
            plugin_id: The plugin ID.
        """
        self._granted_permissions.pop(plugin_id, None)

    def check_permission(self, manifest: PluginManifest, permission: Permission) -> bool:
        """Check if a plugin has a specific permission.

        Args:
            manifest: Plugin manifest with declared permissions.
            permission: The permission to check.

        Returns:
            True if the permission is granted.

        Raises:
            PluginPermissionError: If the permission is not granted.
        """
        granted = self._granted_permissions.get(manifest.id, set())

        # Check if permission was requested in manifest
        if permission not in manifest.permissions:
            raise PluginPermissionError(
                f"Plugin '{manifest.id}' attempted to use permission "
                f"'{permission.value}' which was not declared in its manifest",
                manifest.id,
            )

        # Check if permission was granted
        if permission not in granted:
            raise PluginPermissionError(
                f"Plugin '{manifest.id}' attempted to use permission "
                f"'{permission.value}' which was not granted",
                manifest.id,
            )

        return True

    def resolve_path(self, manifest: PluginManifest, user_path: str | Path) -> Path:
        """Resolve and validate a file path for a plugin.

        Ensures the path is within allowed directories and not a
        path traversal attack.

        Args:
            manifest: Plugin manifest.
            user_path: The path to resolve.

        Returns:
            Resolved absolute path.

        Raises:
            PluginPermissionError: If path is outside allowed directories.
        """
        resolved = Path(user_path).resolve()

        # Check path traversal
        if ".." in str(user_path):
            raise PluginPermissionError(
                f"Path traversal detected in plugin '{manifest.id}': {user_path}",
                manifest.id,
            )

        if not self._allowed_dirs:
            return resolved

        # Check if path is within allowed directories
        is_allowed = any(
            str(resolved).startswith(str(allowed_dir))
            for allowed_dir in self._allowed_dirs
        )

        if not is_allowed:
            raise PluginPermissionError(
                f"Plugin '{manifest.id}' attempted to access path '{resolved}' "
                f"which is outside allowed directories",
                manifest.id,
            )

        return resolved

    def validate_network_access(self, manifest: PluginManifest, url: str) -> bool:
        """Validate network access for a plugin.

        Args:
            manifest: Plugin manifest.
            url: The URL to check.

        Returns:
            True if network access is allowed.

        Raises:
            PluginPermissionError: If network access is not granted.
        """
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        is_local = host in ("localhost", "127.0.0.1", "::1")

        if is_local:
            # Localhost: NETWORK_LOCALHOST (specific) or NETWORK (superset)
            if Permission.NETWORK_LOCALHOST in manifest.permissions:
                self.check_permission(manifest, Permission.NETWORK_LOCALHOST)
                return True
            if Permission.NETWORK in manifest.permissions:
                self.check_permission(manifest, Permission.NETWORK)
                return True
        else:
            # External: only full NETWORK permission works
            granted = self._granted_permissions.get(manifest.id, set())
            if Permission.NETWORK in manifest.permissions and Permission.NETWORK in granted:
                self.check_permission(manifest, Permission.NETWORK)
                return True
            # If only NETWORK_LOCALHOST is granted, reject with localhost hint
            if Permission.NETWORK_LOCALHOST in manifest.permissions and Permission.NETWORK_LOCALHOST in granted:
                raise PluginPermissionError(
                    f"Plugin '{manifest.id}' attempted to access '{url}' "
                    f"which is not localhost (only localhost network allowed)",
                    manifest.id,
                )
            # Check-declared-but-not-granted for NETWORK
            if Permission.NETWORK in manifest.permissions:
                self.check_permission(manifest, Permission.NETWORK)

        raise PluginPermissionError(
            f"Plugin '{manifest.id}' attempted network access to '{url}' "
            f"but did not declare network permissions",
            manifest.id,
        )

    def validate_model_access(self, manifest: PluginManifest, model_id: str) -> bool:
        """Validate that a plugin can access a specific model.

        Args:
            manifest: Plugin manifest.
            model_id: The model ID to check.

        Returns:
            True if model access is allowed.

        Raises:
            PluginPermissionError: If model access is not declared.
        """
        self.check_permission(manifest, Permission.MODEL_ACCESS)

        # Check model is declared in manifest
        declared_models = {m.id for m in manifest.models}
        if declared_models and model_id not in declared_models:
            raise PluginPermissionError(
                f"Plugin '{manifest.id}' attempted to access model '{model_id}' "
                f"which is not declared in its manifest. Declared models: {declared_models}",
                manifest.id,
            )

        return True

    def validate_config(self, manifest: PluginManifest, config: dict[str, Any]) -> list[str]:
        """Validate plugin configuration against its config schema.

        Args:
            manifest: Plugin manifest with config_schema.
            config: The configuration dictionary to validate.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []
        schema = manifest.config_schema

        if not schema:
            return errors

        for key, field_schema in schema.items():
            if field_schema.get("required", False) and key not in config:
                errors.append(f"Missing required config field: '{key}'")

            if key in config:
                expected_type = field_schema.get("type", "string")
                value = config[key]
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Config field '{key}' should be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"Config field '{key}' should be an integer")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Config field '{key}' should be a boolean")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Config field '{key}' should be a number")

                # Check enum values
                enum_values = field_schema.get("enum", [])
                if enum_values and value not in enum_values:
                    errors.append(
                        f"Config field '{key}' value '{value}' is not in allowed values: {enum_values}"
                    )

        return errors

    def set_allowed_directories(self, directories: list[str | Path]) -> None:
        """Set the allowed directories for plugin filesystem access.

        Args:
            directories: List of allowed directory paths.
        """
        self._allowed_dirs = [Path(d).resolve() for d in directories]

    def get_granted_permissions(self, plugin_id: str) -> list[Permission]:
        """Get all granted permissions for a plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            List of granted permissions.
        """
        return list(self._granted_permissions.get(plugin_id, set()))
