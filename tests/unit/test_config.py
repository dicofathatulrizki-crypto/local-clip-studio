"""
Tests for the configuration system (backend/config/settings.py).

Covers:
- Default values
- Environment variable overrides
- Settings file loading
- Validation rules
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.config.defaults import (
    DEFAULT_GPU_BACKEND,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PORT,
    DEFAULT_STORAGE_PATH,
)
from backend.config.settings import Settings, get_settings, reload_settings


class TestSettingsDefaults:
    """Verify that default values are correct."""

    def test_default_host(self):
        settings = Settings()
        assert settings.host == DEFAULT_HOST

    def test_default_port(self):
        settings = Settings()
        assert settings.port == DEFAULT_PORT

    def test_default_log_level(self):
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_gpu_backend(self):
        settings = Settings()
        assert settings.gpu.backend == DEFAULT_GPU_BACKEND

    def test_default_storage_path(self):
        settings = Settings()
        assert settings.storage.app_directory == DEFAULT_STORAGE_PATH

    def test_gpu_memory_limit_default(self):
        settings = Settings()
        assert settings.gpu.memory_limit_percent == 80

    def test_gpu_memory_limit_bounds(self):
        with pytest.raises(Exception):
            Settings(**{"gpu": {"memory_limit_percent": 5}})
        with pytest.raises(Exception):
            Settings(**{"gpu": {"memory_limit_percent": 105}})


class TestSettingsEnvOverride:
    """Verify that environment variables override defaults."""

    def test_env_host_override(self, monkeypatch):
        monkeypatch.setenv("LOCALCLIP_HOST", "0.0.0.0")
        settings = reload_settings()
        assert settings.host == "0.0.0.0"

    def test_env_port_override(self, monkeypatch):
        monkeypatch.setenv("LOCALCLIP_PORT", "9000")
        settings = reload_settings()
        assert settings.port == 9000

    def test_env_log_level(self, monkeypatch):
        monkeypatch.setenv("LOCALCLIP_LOG_LEVEL", "DEBUG")
        settings = reload_settings()
        assert settings.log_level == "DEBUG"

    def test_env_invalid_log_level(self, monkeypatch):
        monkeypatch.setenv("LOCALCLIP_LOG_LEVEL", "INVALID")
        with pytest.raises(Exception):
            reload_settings()

    def test_env_gpu_backend(self, monkeypatch):
        monkeypatch.setenv("LOCALCLIP_GPU__BACKEND", "mps")
        settings = reload_settings()
        assert settings.gpu.backend == "mps"


class TestSettingsFileLoading:
    """Verify that settings file values are loaded and merged."""

    def test_settings_file_loading(self, temp_dir: Path, monkeypatch):
        config_dir = temp_dir / ".localclip" / "config"
        config_dir.mkdir(parents=True)
        settings_file = config_dir / "settings.json"

        file_content = {
            "storage": {
                "app_directory": str(temp_dir / "custom_storage"),
                "max_project_size_gb": 500,
            },
            "gpu": {
                "backend": "rocm",
                "memory_limit_percent": 50,
            },
        }
        settings_file.write_text(json.dumps(file_content))

        monkeypatch.setenv("HOME", str(temp_dir))
        settings = reload_settings()

        assert settings.gpu.backend == "rocm"
        assert settings.storage.max_project_size_gb == 500

    def test_settings_file_corrupted(self, temp_dir: Path, monkeypatch):
        config_dir = temp_dir / ".localclip" / "config"
        config_dir.mkdir(parents=True)
        settings_file = config_dir / "settings.json"
        settings_file.write_text("not valid json")

        monkeypatch.setenv("HOME", str(temp_dir))
        # Should not crash — just log a warning and use defaults
        settings = reload_settings()
        assert settings.host == DEFAULT_HOST  # Defaults should work

    def test_settings_file_missing(self, monkeypatch):
        """Missing settings file should not cause errors."""
        monkeypatch.delenv("LOCALCLIP_HOST", raising=False)
        settings = reload_settings()
        assert settings.host == DEFAULT_HOST


class TestSettingsExport:
    """Verify settings serialization and save."""

    def test_to_dict(self):
        settings = Settings()
        d = settings.to_dict()
        assert isinstance(d, dict)
        assert "gpu" in d
        assert "storage" in d
        assert "host" in d

    def test_save_and_reload(self, temp_dir: Path, monkeypatch):
        monkeypatch.setenv("HOME", str(temp_dir))
        settings = reload_settings()
        settings.gpu.backend = "mps"
        settings.save()

        # Verify file was written
        config_file = Path(temp_dir) / ".localclip" / "config" / "settings.json"
        assert config_file.exists()

        # Reload and verify
        settings2 = reload_settings()
        assert settings2.gpu.backend == "mps"


class TestSettingsSingleton:
    """Verify that get_settings() returns a singleton."""

    def test_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload_creates_new(self):
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2
