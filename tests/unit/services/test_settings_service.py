"""Unit tests for SettingsService (SRS §10.6).

All infrastructure mocked — no database, filesystem, or FastAPI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config.encryption import APIKeyEncryption
from backend.infrastructure.errors import ValidationError
from backend.services.settings_service import (
    SettingValidationError,
    SettingsService,
    _VALID_CATEGORIES,
)


@pytest.fixture
def mock_repo():
    r = MagicMock()
    r.get_value = AsyncMock()
    r.set_value = AsyncMock()
    r.get_all = AsyncMock(return_value={})
    r.get_group = AsyncMock(return_value={})
    r.set_bulk = AsyncMock()
    r.delete_key = AsyncMock(return_value=True)
    r.delete_group = AsyncMock(return_value=0)
    return r


@pytest.fixture
def mock_crypto():
    c = MagicMock(spec=APIKeyEncryption)
    c.encrypt = MagicMock(side_effect=lambda v: f"enc:{v}")
    c.decrypt = MagicMock(side_effect=lambda v: v.replace("enc:", ""))
    c.is_encrypted = MagicMock(side_effect=lambda v: v.startswith("enc:"))
    return c


@pytest.fixture
def service(mock_repo, mock_crypto):
    return SettingsService(mock_repo, mock_crypto)


# ==================================================================
# get_setting
# ==================================================================

class TestGetSetting:
    async def test_get_existing(self, service, mock_repo):
        mock_repo.get_value.return_value = "dark"
        result = await service.get_setting("appearance.theme")
        assert result == "dark"
        mock_repo.get_value.assert_awaited_with("appearance.theme")

    async def test_get_missing(self, service, mock_repo):
        mock_repo.get_value.return_value = None
        result = await service.get_setting("nonexistent.key")
        assert result is None

    async def test_get_none_value(self, service, mock_repo):
        mock_repo.get_value.return_value = None
        result = await service.get_setting("null.setting")
        assert result is None


# ==================================================================
# get_all
# ==================================================================

class TestGetAll:
    async def test_get_all_empty(self, service, mock_repo):
        mock_repo.get_all.return_value = {}
        result = await service.get_all()
        assert result == {}

    async def test_get_all_populated(self, service, mock_repo):
        mock_repo.get_all.return_value = {"theme": "dark", "language": "en"}
        result = await service.get_all()
        assert result["theme"] == "dark"
        assert result["language"] == "en"


# ==================================================================
# get_category
# ==================================================================

class TestGetCategory:
    async def test_get_valid_category(self, service, mock_repo):
        mock_repo.get_group.return_value = {"theme": "dark", "accent": "#c89b5e"}
        result = await service.get_category("appearance")
        assert result["theme"] == "dark"

    async def test_get_invalid_category(self, service):
        with pytest.raises(SettingValidationError, match="category"):
            await service.get_category("nonexistent_cat")

    async def test_get_empty_category(self, service):
        with pytest.raises(SettingValidationError, match="Category"):
            await service.get_category("")

    async def test_get_category_all_valid(self, service, mock_repo):
        for cat in _VALID_CATEGORIES:
            mock_repo.get_group = AsyncMock(return_value={})
            result = await service.get_category(cat)
            assert isinstance(result, dict)


# ==================================================================
# set_setting
# ==================================================================

class TestSetSetting:
    async def test_set_string(self, service, mock_repo):
        await service.set_setting("general.language", "en")
        mock_repo.set_value.assert_awaited_with("general.language", "en")

    async def test_set_integer(self, service, mock_repo):
        await service.set_setting("storage.max_cache_gb", 50)
        mock_repo.set_value.assert_awaited_with("storage.max_cache_gb", 50)

    async def test_set_boolean(self, service, mock_repo):
        await service.set_setting("gpu.enabled", True)
        mock_repo.set_value.assert_awaited_with("gpu.enabled", True)

    async def test_set_encrypts_api_key(self, service, mock_repo, mock_crypto):
        await service.set_setting("provider.api_key", "sk-secret-123")
        args, _ = mock_repo.set_value.call_args
        assert args[1] == "enc:sk-secret-123"
        mock_crypto.encrypt.assert_called_with("sk-secret-123")

    async def test_set_plaintext_not_encrypted(self, service, mock_repo, mock_crypto):
        await service.set_setting("general.language", "en")
        args, _ = mock_repo.set_value.call_args
        assert args[1] == "en"

    async def test_set_empty_key(self, service):
        with pytest.raises(SettingValidationError, match="key"):
            await service.set_setting("", "value")

    async def test_set_invalid_size(self, service):
        with pytest.raises(SettingValidationError, match="negative"):
            await service.set_setting("storage.limit_gb", -5)

    async def test_set_invalid_boolean(self, service):
        with pytest.raises(SettingValidationError, match="Boolean"):
            await service.set_setting("gpu.enabled", "yes")

    async def test_set_invalid_port(self, service):
        with pytest.raises(SettingValidationError, match="Port"):
            await service.set_setting("api.port", 80)

    async def test_set_valid_port(self, service, mock_repo):
        await service.set_setting("api.port", 8765)
        mock_repo.set_value.assert_awaited_with("api.port", 8765)


# ==================================================================
# update_settings
# ==================================================================

class TestUpdateSettings:
    async def test_bulk_update(self, service, mock_repo):
        mock_repo.get_all.return_value = {"a": 1, "b": 2}
        result = await service.update_settings({"a": 10, "b": 20})
        assert result["a"] == 1
        mock_repo.set_bulk.assert_awaited_once()

    async def test_update_empty(self, service, mock_repo):
        mock_repo.get_all.return_value = {}
        result = await service.update_settings({})
        assert isinstance(result, dict)

    async def test_update_encrypts_sensitive(self, service, mock_repo, mock_crypto):
        mock_repo.get_all.return_value = {"provider.api_key": "enc:secret"}
        await service.update_settings({"provider.api_key": "new-secret"})
        args, _ = mock_repo.set_bulk.call_args
        assert args[0]["provider.api_key"] == "enc:new-secret"

    async def test_update_rollback_on_failure(self, service, mock_repo):
        mock_repo.set_bulk.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.update_settings({"key": "value"})

    async def test_update_invalid_key(self, service):
        with pytest.raises(SettingValidationError, match="key"):
            await service.update_settings({"": "value"})


# ==================================================================
# reset_setting
# ==================================================================

class TestResetSetting:
    async def test_reset_existing(self, service, mock_repo):
        mock_repo.delete_key.return_value = True
        await service.reset_setting("general.language")
        mock_repo.delete_key.assert_awaited_with("general.language")

    async def test_reset_missing(self, service, mock_repo):
        mock_repo.delete_key.return_value = False
        await service.reset_setting("nonexistent.key")
        mock_repo.delete_key.assert_awaited_with("nonexistent.key")

    async def test_reset_empty_key(self, service):
        with pytest.raises(SettingValidationError, match="key"):
            await service.reset_setting("")


# ==================================================================
# reset_category
# ==================================================================

class TestResetCategory:
    async def test_reset_valid_category(self, service, mock_repo):
        mock_repo.delete_group.return_value = 3
        mock_repo.get_all.return_value = {}
        result = await service.reset_category("storage")
        assert isinstance(result, dict)

    async def test_reset_invalid_category(self, service):
        with pytest.raises(SettingValidationError, match="category"):
            await service.reset_category("bad")

    async def test_reset_empty_category(self, service):
        with pytest.raises(SettingValidationError, match="Category"):
            await service.reset_category("")


# ==================================================================
# reset_all
# ==================================================================

class TestResetAll:
    async def test_reset_all(self, service, mock_repo):
        result = await service.reset_all()
        assert result == {}
        assert mock_repo.delete_group.call_count >= 1

    async def test_reset_all_empty(self, service, mock_repo):
        mock_repo.delete_group.return_value = 0
        result = await service.reset_all()
        assert result == {}


# ==================================================================
# validate_setting / validate_category
# ==================================================================

class TestValidation:
    async def test_validate_setting_valid(self, service):
        assert service.validate_setting("general.language", "en") is True

    async def test_validate_setting_invalid_key(self, service):
        with pytest.raises(SettingValidationError, match="key"):
            service.validate_setting("", "value")

    async def test_validate_setting_invalid_boolean(self, service):
        with pytest.raises(SettingValidationError, match="Boolean"):
            service.validate_setting("gpu.enabled", 1)

    async def test_validate_setting_invalid_size(self, service):
        with pytest.raises(SettingValidationError, match="negative"):
            service.validate_setting("cache.limit_gb", -10)

    async def test_validate_setting_dot_patterns(self, service):
        with pytest.raises(SettingValidationError, match="dot"):
            service.validate_setting("..key", "value")
        with pytest.raises(SettingValidationError, match="dot"):
            service.validate_setting(".key", "value")
        with pytest.raises(SettingValidationError, match="dot"):
            service.validate_setting("key.", "value")
        with pytest.raises(SettingValidationError, match="dot"):
            service.validate_setting("a..b", "value")

    async def test_validate_category_valid(self, service):
        assert service.validate_category("storage") is True

    async def test_validate_category_invalid(self, service):
        with pytest.raises(SettingValidationError, match="category"):
            service.validate_category("nonexistent")


# ==================================================================
# import/export
# ==================================================================

class TestImportExport:
    async def test_export_success(self, service, mock_repo, mock_crypto):
        mock_repo.get_all.return_value = {
            "general.language": "en",
            "provider.api_key": "enc:sk-secret",
        }
        result = await service.export_settings()
        assert isinstance(result, str)
        assert "en" in result
        assert "sk-secret" in result

    async def test_import_valid(self, service, mock_repo):
        mock_repo.get_all.return_value = {"theme": "dark"}
        result = await service.import_settings('{"theme": "light"}')
        assert isinstance(result, dict)

    async def test_import_malformed_json(self, service):
        with pytest.raises(ValidationError, match="JSON"):
            await service.import_settings("{invalid}")

    async def test_import_non_dict(self, service):
        with pytest.raises(ValidationError, match="object"):
            await service.import_settings('"string"')

    async def test_import_empty(self, service, mock_repo):
        mock_repo.get_all.return_value = {}
        result = await service.import_settings("{}")
        assert isinstance(result, dict)


# ==================================================================
# Provider settings
# ==================================================================

class TestProviderSettings:
    async def test_get_provider(self, service, mock_repo, mock_crypto):
        mock_repo.get_group.return_value = {"api_key": "enc:sk-test", "model": "gpt-4"}
        result = await service.get_provider_settings("openai")
        assert result["api_key"] == "sk-test"
        assert result["model"] == "gpt-4"

    async def test_set_provider(self, service, mock_repo, mock_crypto):
        await service.set_provider_settings("openai", {"api_key": "sk-new", "model": "gpt-4"})
        args, _ = mock_repo.set_bulk.call_args
        assert "enc:sk-new" in str(args[0])

    async def test_get_provider_empty(self, service, mock_repo):
        mock_repo.get_group.return_value = {}
        result = await service.get_provider_settings("nonexistent")
        assert result == {}


# ==================================================================
# Model settings
# ==================================================================

class TestModelSettings:
    async def test_get_model(self, service, mock_repo):
        mock_repo.get_group.return_value = {"vram_mb": "4096"}
        result = await service.get_model_settings("whisper-large-v3")
        assert result["vram_mb"] == "4096"

    async def test_set_model(self, service, mock_repo):
        await service.set_model_settings("yolov8n", {"vram_mb": 512})
        mock_repo.set_bulk.assert_awaited_once()
        args, _ = mock_repo.set_bulk.call_args
        assert "model.yolov8n.vram_mb" in args[0]


# ==================================================================
# Repository failures
# ==================================================================

class TestRepositoryFailures:
    async def test_get_value_failure(self, service, mock_repo):
        mock_repo.get_value.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.get_setting("any.key")

    async def test_set_value_failure(self, service, mock_repo):
        mock_repo.set_value.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.set_setting("key", "value")

    async def test_bulk_update_rollback(self, service, mock_repo):
        mock_repo.set_bulk.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.update_settings({"a": 1})

    async def test_delete_key_failure(self, service, mock_repo):
        mock_repo.delete_key.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.reset_setting("any.key")


# ==================================================================
# Logging verification
# ==================================================================

class TestLogging:
    async def test_set_setting_logs(self, service, mock_repo):
        with patch("backend.services.settings_service.logger") as mock_log:
            await service.set_setting("general.language", "en")
            mock_log.info.assert_called()

    async def test_reset_setting_logs(self, service, mock_repo):
        with patch("backend.services.settings_service.logger") as mock_log:
            await service.reset_setting("general.language")
            mock_log.info.assert_called()

    async def test_import_settings_logs(self, service, mock_repo):
        with patch("backend.services.settings_service.logger") as mock_log:
            mock_repo.get_all.return_value = {}
            await service.import_settings('{"theme": "dark"}')
            mock_log.info.assert_called()

    async def test_export_settings_logs(self, service, mock_repo):
        with patch("backend.services.settings_service.logger") as mock_log:
            mock_repo.get_all.return_value = {"theme": "dark"}
            await service.export_settings()
            mock_log.info.assert_called()


# ==================================================================
# Edge cases
# ==================================================================

class TestEdgeCases:
    async def test_unicode_values(self, service, mock_repo):
        await service.set_setting("general.language", "中文")
        mock_repo.set_value.assert_awaited_with("general.language", "中文")

    async def test_none_setting(self, service, mock_repo):
        await service.set_setting("nullable.key", None)
        mock_repo.set_value.assert_awaited_with("nullable.key", None)

    async def test_long_key(self, service):
        with pytest.raises(SettingValidationError, match="255"):
            service.validate_setting("x" * 256, "value")

    async def test_oversized_value(self, service, mock_repo):
        with pytest.raises(SettingValidationError, match="negative"):
            await service.set_setting("export.max_size_gb", -1)
