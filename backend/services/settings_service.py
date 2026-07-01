"""Settings Service — application settings management (SRS §10.6).

Clean Architecture: depends only on repository abstractions, encryption infrastructure.
No SQLAlchemy, no FastAPI, no HTTP logic.
"""

from __future__ import annotations

import json
from typing import Any

from backend.config.encryption import APIKeyEncryption
from backend.infrastructure.database.repositories.settings_repo import SettingsRepository
from backend.infrastructure.errors import ValidationError
from backend.infrastructure.logging.logger import get_logger

logger = get_logger("backend.services.settings_service")

_SENSITIVE_KEYS = {"api_key", "api_secret", "provider.api_key", "provider.secret", "auth.token"}
_VALID_CATEGORIES = {"general", "appearance", "storage", "gpu", "ai_models",
                     "export", "keyboard", "cache", "advanced", "provider", "model"}


class SettingValidationError(ValidationError):
    """Raised when a setting value fails validation."""
    code: str = "ERR-SETTINGS-001"
    message: str = "Setting validation failed"


class SettingsService:
    """Application settings management — SRS §10.6.

    Responsibilities:
    - Read/write settings via SettingsRepository
    - Category-scoped access and updates
    - Merge semantics for bulk updates
    - Encryption of sensitive values (API keys, secrets)
    - Validation rules for setting values
    - Settings import/export
    - Provider and model configuration
    """

    def __init__(
        self,
        settings_repository: SettingsRepository,
        api_key_encryption: APIKeyEncryption | None = None,
    ) -> None:
        self._repo = settings_repository
        self._crypto = api_key_encryption or APIKeyEncryption()

    # ------------------------------------------------------------------
    # Public API — SRS §10.6
    # ------------------------------------------------------------------

    async def get_all(self) -> dict[str, Any]:
        """Get all settings.

        Returns:
            Flat dictionary of all settings.
        """
        return await self._repo.get_all()

    async def get_category(self, category: str) -> dict[str, Any]:
        """Get all settings for a specific category.

        Args:
            category: Category name (e.g., 'storage', 'gpu', 'export').

        Returns:
            Dictionary of settings in that category (keys without prefix).

        Raises:
            ValidationError: If category is invalid.
        """
        self._validate_category(category)
        return await self._repo.get_group(category)

    async def get_setting(self, key: str) -> Any | None:
        """Get a single setting by key.

        Args:
            key: Dot-separated setting key.

        Returns:
            The setting value, or None if not found.
        """
        return await self._repo.get_value(key)

    async def set_setting(self, key: str, value: Any) -> None:
        """Set a single setting value.

        Args:
            key: Dot-separated setting key.
            value: Any JSON-encodable value.

        Raises:
            ValidationError: If key or value is invalid.
        """
        self._validate_key(key)
        self._validate_value(key, value)

        if self._is_sensitive(key):
            value = self._crypto.encrypt(str(value))

        await self._repo.set_value(key, value)
        logger.info("Setting updated", extra={"extra_fields": {"key": key, "event": "setting.updated"}})

    async def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update multiple settings atomically (merge semantics).

        Args:
            updates: Dict of key-value pairs to set. Keys use dot notation.

        Returns:
            Complete settings dict after merge.

        Raises:
            ValidationError: If any key or value is invalid.
            RepositoryError: On persistence failure (rolls back).
        """
        for key in updates:
            self._validate_key(key)
            self._validate_value(key, updates[key])

        encrypted: dict[str, Any] = {}
        for key, value in updates.items():
            if self._is_sensitive(key):
                encrypted[key] = self._crypto.encrypt(str(value))
            else:
                encrypted[key] = value

        try:
            await self._repo.set_bulk(encrypted)
        except Exception:
            logger.error("Settings bulk update failed, rolling back", extra={"extra_fields": {"keys": list(updates.keys())}})
            raise

        logger.info("Settings updated", extra={"extra_fields": {"count": len(updates), "event": "settings.bulk_updated"}})
        return await self._repo.get_all()

    async def reset_setting(self, key: str) -> None:
        """Reset a single setting to its default (deletes it).

        Args:
            key: Setting key to reset.

        Raises:
            ValidationError: If key is invalid.
        """
        self._validate_key(key)
        deleted = await self._repo.delete_key(key)
        if deleted:
            logger.info("Setting reset", extra={"extra_fields": {"key": key, "event": "setting.reset"}})

    async def reset_category(self, category: str) -> dict[str, Any]:
        """Reset all settings in a category.

        Args:
            category: Category name to reset.

        Returns:
            Remaining settings after deletion.

        Raises:
            ValidationError: If category is invalid.
        """
        self._validate_category(category)
        count = await self._repo.delete_group(category)
        if count > 0:
            logger.info("Category reset", extra={"extra_fields": {"category": category, "count": count, "event": "category.reset"}})
        return await self._repo.get_all()

    async def reset_all(self) -> dict[str, Any]:
        """Reset all settings (clears all entries).

        Returns:
            Empty settings dict.
        """
        for category in _VALID_CATEGORIES:
            await self._repo.delete_group(category)
        logger.info("All settings reset", extra={"extra_fields": {"event": "settings.all_reset"}})
        return {}

    async def export_settings(self) -> str:
        """Export all settings as a JSON string.

        Sensitive values are decrypted before export.

        Returns:
            JSON string of all settings.
        """
        all_settings = await self._repo.get_all()
        decrypted = {}
        for key, value in all_settings.items():
            if self._is_sensitive(key) and isinstance(value, str):
                try:
                    decrypted[key] = self._crypto.decrypt(value)
                except ValueError:
                    decrypted[key] = value
            else:
                decrypted[key] = value
        logger.info("Settings exported", extra={"extra_fields": {"count": len(decrypted), "event": "settings.exported"}})
        return json.dumps(decrypted, indent=2, default=str)

    async def import_settings(self, config_json: str) -> dict[str, Any]:
        """Import settings from a JSON string.

        Args:
            config_json: JSON string of settings to import (merge semantics).

        Returns:
            Complete settings dict after import.

        Raises:
            ValidationError: If JSON is invalid or values fail validation.
        """
        try:
            settings = json.loads(config_json)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message=f"Invalid JSON: {exc}",
                details={"error": str(exc)},
            )
        if not isinstance(settings, dict):
            raise ValidationError(message="Settings must be a JSON object", details={"type": type(settings).__name__})
        return await self.update_settings(settings)

    # ------------------------------------------------------------------
    # Provider settings
    # ------------------------------------------------------------------

    async def get_provider_settings(self, provider_id: str) -> dict[str, Any]:
        """Get all settings for a specific AI provider.

        Args:
            provider_id: Provider identifier (e.g., 'openai', 'local').

        Returns:
            Provider settings dict with decrypted secrets.
        """
        prefix = f"provider.{provider_id}"
        raw = await self._repo.get_group(prefix)
        decrypted = {}
        for key, value in raw.items():
            if isinstance(value, str) and self._crypto.is_encrypted(value):
                try:
                    decrypted[key] = self._crypto.decrypt(value)
                except ValueError:
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted

    async def set_provider_settings(self, provider_id: str, settings: dict[str, Any]) -> None:
        """Set settings for a specific AI provider.

        Sensitive fields are encrypted before storage.

        Args:
            provider_id: Provider identifier.
            settings: Provider configuration dict.
        """
        prefix = f"provider.{provider_id}"
        encrypted: dict[str, Any] = {}
        for key, value in settings.items():
            full_key = f"{prefix}.{key}"
            self._validate_key(full_key)
            if self._is_sensitive(key):
                encrypted[full_key] = self._crypto.encrypt(str(value))
            else:
                encrypted[full_key] = value
        await self._repo.set_bulk(encrypted)
        logger.info("Provider settings updated", extra={"extra_fields": {"provider_id": provider_id, "event": "provider.settings_updated"}})

    # ------------------------------------------------------------------
    # Model settings
    # ------------------------------------------------------------------

    async def get_model_settings(self, model_id: str) -> dict[str, Any]:
        """Get settings for a specific AI model.

        Args:
            model_id: Model identifier (e.g., 'whisper-large-v3').

        Returns:
            Model settings dict.
        """
        prefix = f"model.{model_id}"
        return await self._repo.get_group(prefix)

    async def set_model_settings(self, model_id: str, settings: dict[str, Any]) -> None:
        """Set settings for a specific AI model.

        Args:
            model_id: Model identifier.
            settings: Model configuration dict.
        """
        prefix = f"model.{model_id}"
        prefixed = {f"{prefix}.{k}": v for k, v in settings.items()}
        for key in prefixed:
            self._validate_key(key)
        await self._repo.set_bulk(prefixed)
        logger.info("Model settings updated", extra={"extra_fields": {"model_id": model_id, "event": "model.settings_updated"}})

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_setting(self, key: str, value: Any) -> bool:
        """Validate a setting key and value without persisting.

        Args:
            key: Setting key.
            value: Setting value.

        Returns:
            True if valid.

        Raises:
            SettingValidationError: If validation fails.
        """
        self._validate_key(key)
        self._validate_value(key, value)
        return True

    def validate_category(self, category: str) -> bool:
        """Validate a category name.

        Args:
            category: Category name.

        Returns:
            True if valid.

        Raises:
            SettingValidationError: If category is invalid.
        """
        self._validate_category(category)
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_key(self, key: str) -> None:
        """Validate a setting key format."""
        if not key or not isinstance(key, str):
            raise SettingValidationError(
                message="Setting key must be a non-empty string",
                details={"key": key},
            )
        if len(key) > 255:
            raise SettingValidationError(
                message="Setting key must be 255 characters or fewer",
                details={"key": key, "max_length": 255},
            )
        if ".." in key or key.startswith(".") or key.endswith("."):
            raise SettingValidationError(
                message="Setting key contains invalid dot patterns",
                details={"key": key},
            )

    def _validate_value(self, key: str, value: Any) -> None:
        """Validate a setting value based on its key."""
        if key.endswith(".max_size_gb") or key.endswith(".limit_gb"):
            if not isinstance(value, (int, float)) or value < 0:
                raise SettingValidationError(
                    message=f"Size limit must be a non-negative number",
                    details={"key": key, "value": value},
                )
        if key.endswith(".enabled") or key.endswith(".auto") or key.endswith(".include_captions"):
            if not isinstance(value, bool):
                raise SettingValidationError(
                    message=f"Boolean setting must be true or false",
                    details={"key": key, "value": value, "type": type(value).__name__},
                )
        if key.endswith(".port"):
            if not isinstance(value, int) or value < 1024 or value > 65535:
                raise SettingValidationError(
                    message=f"Port must be an integer between 1024 and 65535",
                    details={"key": key, "value": value},
                )

    def _validate_category(self, category: str) -> None:
        """Validate a category name."""
        if not category or not isinstance(category, str):
            raise SettingValidationError(
                message="Category must be a non-empty string",
                details={"category": category},
            )
        if category not in _VALID_CATEGORIES:
            raise SettingValidationError(
                message=f"Invalid category: '{category}'. Valid categories: {', '.join(sorted(_VALID_CATEGORIES))}",
                details={"category": category, "valid_categories": sorted(_VALID_CATEGORIES)},
            )

    def _is_sensitive(self, key: str) -> bool:
        """Check if a key is sensitive and should be encrypted."""
        key_lower = key.lower()
        for sensitive in _SENSITIVE_KEYS:
            if sensitive in key_lower:
                return True
        return False
