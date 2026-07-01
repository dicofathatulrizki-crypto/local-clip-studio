"""Unit tests for ProviderService (SRS §10.5).

All infrastructure mocked — no database, filesystem, network, or FastAPI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config.encryption import APIKeyEncryption
from backend.domain.entities.provider import Provider
from backend.infrastructure.errors import ConflictError, NotFoundError, ValidationError
from backend.services.provider_service import ProviderNotFoundError, ProviderService


@pytest.fixture
def mock_provider_repo():
    r = MagicMock()
    r.list_all = AsyncMock(return_value=[])
    r.get_domain = AsyncMock()
    r.update_from_domain = AsyncMock()
    r.create_from_domain = AsyncMock()
    r.list_enabled = AsyncMock(return_value=[])
    return r


@pytest.fixture
def mock_model_repo():
    r = MagicMock()
    r.list_by_type = AsyncMock(return_value=[])
    r.list_all = AsyncMock(return_value=[])
    r.get_model = AsyncMock()
    r.register_model = AsyncMock()
    r.unregister_model = AsyncMock()
    r.activate_model = AsyncMock()
    r.deactivate_model = AsyncMock()
    return r


@pytest.fixture
def mock_plugin_registry():
    r = MagicMock()
    r.health_check_all = MagicMock(return_value={})
    r.get_best_provider = MagicMock(return_value=None)
    return r


@pytest.fixture
def mock_crypto():
    c = MagicMock(spec=APIKeyEncryption)
    c.encrypt = MagicMock(side_effect=lambda v: f"enc:{v}")
    c.decrypt = MagicMock(side_effect=lambda v: v.replace("enc:", ""))
    c.is_encrypted = MagicMock(side_effect=lambda v: v.startswith("enc:"))
    return c


@pytest.fixture
def service(mock_provider_repo, mock_model_repo, mock_plugin_registry, mock_crypto):
    return ProviderService(mock_provider_repo, mock_model_repo, mock_plugin_registry, mock_crypto)


@pytest.fixture
def sample_provider():
    return Provider(
        id="test-provider",
        name="Test Provider",
        enabled=True,
        supported_tasks=["stt", "llm"],
        api_key="enc:sk-test",
        base_url="https://api.test.com",
        models={"stt": "whisper-1", "llm": "gpt-4o"},
        defaults={"temperature": 0.7, "max_tokens": 4096, "timeout": 60, "retry_count": 3},
    )


# ==================================================================
# list_providers
# ==================================================================

class TestListProviders:
    async def test_list_empty(self, service, mock_provider_repo):
        mock_provider_repo.list_all.return_value = []
        result = await service.list_providers()
        assert result == []

    async def test_list_populated(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.list_all.return_value = [sample_provider]
        result = await service.list_providers()
        assert len(result) == 1
        assert result[0].id == "test-provider"


# ==================================================================
# get_provider
# ==================================================================

class TestGetProvider:
    async def test_get_existing(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        result = await service.get_provider("test-provider")
        assert result.id == "test-provider"

    async def test_get_missing(self, service, mock_provider_repo):
        mock_provider_repo.get_domain.return_value = None
        with pytest.raises(ProviderNotFoundError):
            await service.get_provider("nonexistent")


# ==================================================================
# configure_provider
# ==================================================================

class TestConfigureProvider:
    async def test_create_new(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = None
        mock_provider_repo.create_from_domain.return_value = sample_provider
        result = await service.configure_provider("test-provider", {
            "name": "Test Provider", "supported_tasks": ["stt", "llm"]
        })
        assert result is not None
        mock_provider_repo.create_from_domain.assert_awaited_once()

    async def test_update_existing(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        mock_provider_repo.update_from_domain.return_value = sample_provider
        result = await service.configure_provider("test-provider", {
            "enabled": False, "base_url": "https://new.url"
        })
        assert result is not None
        mock_provider_repo.update_from_domain.assert_awaited_once()

    async def test_create_empty_provider_id(self, service):
        with pytest.raises(ValidationError, match="required"):
            await service.configure_provider("", {"name": "X"})

    async def test_create_invalid_task(self, service):
        with pytest.raises(ValidationError, match="task"):
            await service.configure_provider("p1", {"name": "X", "supported_tasks": ["invalid_task"]})

    async def test_create_invalid_temperature(self, service):
        with pytest.raises(ValidationError, match="Temperature"):
            await service.configure_provider("p1", {"name": "X", "defaults": {"temperature": 3.0}})

    async def test_update_encrypts_api_key(self, service, mock_provider_repo, sample_provider, mock_crypto):
        mock_provider_repo.get_domain.return_value = sample_provider
        await service.configure_provider("test-provider", {"api_key": "sk-new"})
        mock_crypto.encrypt.assert_called_with("sk-new")


# ==================================================================
# enable_provider / disable_provider
# ==================================================================

class TestEnableDisable:
    async def test_enable(self, service, mock_provider_repo, sample_provider):
        sample_provider.enabled = False
        mock_provider_repo.get_domain.return_value = sample_provider
        mock_provider_repo.update_from_domain.return_value = sample_provider
        result = await service.enable_provider("test-provider")
        assert result is not None
        mock_provider_repo.update_from_domain.assert_awaited_once()

    async def test_disable(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        mock_provider_repo.update_from_domain.return_value = sample_provider
        result = await service.disable_provider("test-provider")
        assert result is not None

    async def test_enable_missing(self, service, mock_provider_repo):
        mock_provider_repo.get_domain.return_value = None
        with pytest.raises(ProviderNotFoundError):
            await service.enable_provider("nonexistent")


# ==================================================================
# validate_provider
# ==================================================================

class TestValidateProvider:
    async def test_valid(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        result = await service.validate_provider("test-provider")
        assert result is True

    async def test_missing_name(self, service, mock_provider_repo):
        p = Provider(id="p1", name="", enabled=False)
        mock_provider_repo.get_domain.return_value = p
        with pytest.raises(ValidationError) as exc:
            await service.validate_provider("p1")
        assert "Provider name is required" in str(exc.value.details.get("errors", []))

    async def test_no_tasks(self, service, mock_provider_repo):
        p = Provider(id="p1", name="X", enabled=False, supported_tasks=[])
        mock_provider_repo.get_domain.return_value = p
        with pytest.raises(ValidationError) as exc:
            await service.validate_provider("p1")
        assert "At least one supported task is required" in str(exc.value.details.get("errors", []))

    async def test_missing_api_key_with_base_url(self, service, mock_provider_repo):
        p = Provider(id="p1", name="X", enabled=True, supported_tasks=["stt"],
                     base_url="https://api.example.com", api_key=None)
        mock_provider_repo.get_domain.return_value = p
        with pytest.raises(ValidationError) as exc:
            await service.validate_provider("p1")
        assert "API key is required" in str(exc.value.details.get("errors", []))


# ==================================================================
# test_connection
# ==================================================================

class TestConnection:
    async def test_connection_success(self, service, mock_provider_repo, mock_plugin_registry, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        mock_plugin_registry.health_check_all.return_value = {"p1": {"status": "ok"}}
        result = await service.test_connection("test-provider")
        assert result["success"] is True

    async def test_connection_missing(self, service, mock_provider_repo):
        mock_provider_repo.get_domain.return_value = None
        with pytest.raises(ProviderNotFoundError):
            await service.test_connection("nonexistent")


# ==================================================================
# get_active_provider / capabilities
# ==================================================================

class TestActiveProvider:
    async def test_active_found(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.list_enabled.return_value = [sample_provider]
        result = await service.get_active_provider("stt")
        assert result is not None
        assert result.id == "test-provider"

    async def test_active_not_found(self, service, mock_provider_repo):
        mock_provider_repo.list_enabled.return_value = []
        result = await service.get_active_provider("stt")
        assert result is None

    async def test_active_invalid_task(self, service):
        with pytest.raises(ValidationError, match="task"):
            await service.get_active_provider("invalid_task")

    async def test_get_capabilities(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        result = await service.get_provider_capabilities("test-provider")
        assert "stt" in result
        assert "llm" in result


# ==================================================================
# Model management
# ==================================================================

class TestModelManagement:
    async def test_list_all_models(self, service, mock_model_repo):
        mock_model_repo.list_all.return_value = [{"id": "m1"}, {"id": "m2"}]
        result = await service.list_models()
        assert len(result) == 2

    async def test_list_by_type(self, service, mock_model_repo):
        mock_model_repo.list_by_type.return_value = [{"id": "m1"}]
        result = await service.list_models("stt")
        assert len(result) == 1

    async def test_register_model(self, service, mock_model_repo):
        mock_model_repo.get_model.return_value = None
        mock_model_repo.register_model.return_value = {"id": "m1", "type": "stt"}
        result = await service.register_model("m1", "local", "stt", 1024)
        assert result["id"] == "m1"

    async def test_register_duplicate(self, service, mock_model_repo):
        mock_model_repo.get_model.return_value = {"id": "m1"}
        with pytest.raises(ConflictError, match="registered"):
            await service.register_model("m1", "local", "stt", 1024)

    async def test_unregister_model(self, service, mock_model_repo):
        mock_model_repo.get_model.return_value = {"id": "m1"}
        await service.unregister_model("m1")
        mock_model_repo.unregister_model.assert_awaited_with("m1")

    async def test_activate_model(self, service, mock_model_repo):
        mock_model_repo.get_model.return_value = {"id": "m1"}
        mock_model_repo.activate_model.return_value = {"id": "m1", "status": "ready"}
        result = await service.activate_model("m1")
        assert result["status"] == "ready"

    async def test_deactivate_model(self, service, mock_model_repo):
        mock_model_repo.get_model.return_value = {"id": "m1"}
        mock_model_repo.deactivate_model.return_value = {"id": "m1", "status": "inactive"}
        result = await service.deactivate_model("m1")
        assert result["status"] == "inactive"


# ==================================================================
# health_check
# ==================================================================

class TestHealthCheck:
    async def test_healthy(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        result = await service.health_check("test-provider")
        assert result["status"] == "ok"
        assert result["healthy"] is True

    async def test_degraded(self, service, mock_provider_repo, sample_provider):
        sample_provider.enabled = False
        mock_provider_repo.get_domain.return_value = sample_provider
        result = await service.health_check("test-provider")
        assert result["status"] == "degraded"


# ==================================================================
# Repository failures
# ==================================================================

class TestRepositoryFailures:
    async def test_list_failure(self, service, mock_provider_repo):
        mock_provider_repo.list_all.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.list_providers()

    async def test_get_failure(self, service, mock_provider_repo):
        mock_provider_repo.get_domain.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.get_provider("p1")

    async def test_update_failure(self, service, mock_provider_repo, sample_provider):
        mock_provider_repo.get_domain.return_value = sample_provider
        mock_provider_repo.update_from_domain.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.enable_provider("p1")


# ==================================================================
# Logging
# ==================================================================

class TestLogging:
    async def test_enable_logs(self, service, mock_provider_repo, sample_provider):
        with patch("backend.services.provider_service.logger") as mock_log:
            mock_provider_repo.get_domain.return_value = sample_provider
            mock_provider_repo.update_from_domain.return_value = sample_provider
            await service.enable_provider("test-provider")
            mock_log.info.assert_called()

    async def test_disable_logs(self, service, mock_provider_repo, sample_provider):
        with patch("backend.services.provider_service.logger") as mock_log:
            mock_provider_repo.get_domain.return_value = sample_provider
            mock_provider_repo.update_from_domain.return_value = sample_provider
            await service.disable_provider("test-provider")
            mock_log.info.assert_called()


# ==================================================================
# Edge cases
# ==================================================================

class TestEdgeCases:
    async def test_provider_with_no_models(self, service, mock_provider_repo):
        p = Provider(id="no-models", name="No Models", enabled=True, supported_tasks=["stt"])
        mock_provider_repo.get_domain.return_value = p
        result = await service.get_provider("no-models")
        assert result.models == {}

    async def test_provider_with_no_tasks(self, service, mock_provider_repo):
        p = Provider(id="no-tasks", name="No Tasks", enabled=True)
        mock_provider_repo.get_domain.return_value = p
        result = await service.get_provider_capabilities("no-tasks")
        assert result == []
