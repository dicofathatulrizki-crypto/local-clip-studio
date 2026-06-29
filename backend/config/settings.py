"""
Pydantic-based settings for Local Clip Studio.

Settings are loaded from:
1. Default values (backend/config/defaults.py)
2. settings.json file (~/.localclip/config/settings.json)
3. Environment variables (LOCALCLIP_*)

Later sources override earlier ones.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.config.defaults import (
    DEFAULT_AUTO_SAVE_INTERVAL_SECONDS,
    DEFAULT_CACHE_RETENTION_DAYS,
    DEFAULT_CELERY_BROKER_URL,
    DEFAULT_CELERY_WORKER_COUNT,
    DEFAULT_CLEANUP_ENABLED,
    DEFAULT_CLEANUP_INTERVAL_HOURS,
    DEFAULT_ENABLE_CPU_FALLBACK,
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_EXPORT_GPU_ENCODING,
    DEFAULT_EXPORT_PRESET,
    DEFAULT_GPU_BACKEND,
    DEFAULT_GPU_MEMORY_LIMIT_PERCENT,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CACHE_SIZE_GB,
    DEFAULT_MAX_CONCURRENT_JOBS,
    DEFAULT_MAX_FILE_SIZE_GB,
    DEFAULT_MAX_LOG_SIZE_MB,
    DEFAULT_MAX_MODEL_STORAGE_GB,
    DEFAULT_MAX_PLUGIN_MEMORY_MB,
    DEFAULT_MAX_PROJECT_SIZE_GB,
    DEFAULT_MAX_TEMP_SIZE_GB,
    DEFAULT_PORT,
    DEFAULT_STORAGE_PATH,
    DEFAULT_STT_MODEL,
    DEFAULT_TEMP_RETENTION_HOURS,
    DEFAULT_VERSION_HISTORY_COUNT,
)

# ─── Singleton ────────────────────────────────────────────────────────────
_settings_instance: "Settings | None" = None


# ─── Nested Settings Models ──────────────────────────────────────────────


class GPUConfig(BaseModel):
    """GPU and hardware acceleration configuration."""

    backend: str = Field(default=DEFAULT_GPU_BACKEND, description="GPU backend: auto, cuda, mps, rocm, cpu")
    memory_limit_percent: int = Field(
        default=DEFAULT_GPU_MEMORY_LIMIT_PERCENT,
        ge=10,
        le=100,
        description="Maximum GPU memory usage percentage",
    )
    enable_cpu_fallback: bool = Field(
        default=DEFAULT_ENABLE_CPU_FALLBACK,
        description="Fall back to CPU if GPU unavailable",
    )


class StorageConfig(BaseModel):
    """Storage and file management configuration."""

    app_directory: Path = Field(default=DEFAULT_STORAGE_PATH, description="Application data directory")
    max_project_size_gb: int = Field(default=DEFAULT_MAX_PROJECT_SIZE_GB, ge=1, description="Max size per project in GB")
    max_cache_size_gb: int = Field(default=DEFAULT_MAX_CACHE_SIZE_GB, ge=1, description="Max cache size in GB")
    max_model_storage_gb: int = Field(default=DEFAULT_MAX_MODEL_STORAGE_GB, ge=1, description="Max model storage in GB")
    max_log_size_mb: int = Field(default=DEFAULT_MAX_LOG_SIZE_MB, ge=10, description="Max log file size in MB")
    max_temp_size_gb: int = Field(default=DEFAULT_MAX_TEMP_SIZE_GB, ge=1, description="Max temp file size in GB")
    max_file_size_gb: int = Field(default=DEFAULT_MAX_FILE_SIZE_GB, ge=1, description="Max single file import size in GB")
    auto_cleanup_enabled: bool = Field(default=DEFAULT_CLEANUP_ENABLED, description="Enable automatic cleanup")
    cleanup_interval_hours: int = Field(default=DEFAULT_CLEANUP_INTERVAL_HOURS, ge=1, description="Cleanup interval in hours")
    temp_retention_hours: int = Field(default=DEFAULT_TEMP_RETENTION_HOURS, ge=1, description="Temp file retention in hours")
    cache_retention_days: int = Field(default=DEFAULT_CACHE_RETENTION_DAYS, ge=1, description="Cache retention in days")


class PipelineConfig(BaseModel):
    """AI pipeline configuration."""

    default_stt_model: str = Field(default=DEFAULT_STT_MODEL, description="Default speech-to-text model")
    stage_timeout_minutes: int = Field(default=30, ge=1, le=120, description="Per-stage timeout in minutes")
    max_concurrent_jobs: int = Field(default=DEFAULT_MAX_CONCURRENT_JOBS, ge=1, le=8, description="Max concurrent pipeline jobs")
    max_plugin_memory_mb: int = Field(default=DEFAULT_MAX_PLUGIN_MEMORY_MB, ge=256, description="Max plugin memory in MB")


class ExportConfig(BaseModel):
    """Export configuration."""

    default_format: str = Field(default=DEFAULT_EXPORT_FORMAT, description="Default export format")
    default_preset: str = Field(default=DEFAULT_EXPORT_PRESET, description="Default export quality preset")
    gpu_encoding: bool = Field(default=DEFAULT_EXPORT_GPU_ENCODING, description="Use GPU acceleration for encoding")


class AutoSaveConfig(BaseModel):
    """Auto-save and version configuration."""

    interval_seconds: int = Field(default=DEFAULT_AUTO_SAVE_INTERVAL_SECONDS, ge=10, le=600, description="Auto-save interval in seconds")
    version_history_count: int = Field(default=DEFAULT_VERSION_HISTORY_COUNT, ge=1, le=100, description="Number of versions to retain")


# ─── Main Settings ───────────────────────────────────────────────────────


class Settings(BaseSettings):
    """
    Application settings for Local Clip Studio.

    Loaded from: defaults → settings.json → environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="LOCALCLIP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=False,
    )

    # ── Server ──
    host: str = Field(default=DEFAULT_HOST, description="Server bind host")
    port: int = Field(default=DEFAULT_PORT, ge=1024, le=65535, description="Server bind port")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default=DEFAULT_LOG_LEVEL, description="Logging level")

    # ── Nested Configs ──
    gpu: GPUConfig = Field(default_factory=GPUConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    auto_save: AutoSaveConfig = Field(default_factory=AutoSaveConfig)

    # ── Celery ──
    celery_broker_url: str = Field(default=DEFAULT_CELERY_BROKER_URL, description="Celery broker URL")
    celery_worker_count: int = Field(default=DEFAULT_CELERY_WORKER_COUNT, ge=1, le=16, description="Celery worker count")

    # ── Paths ──
    ffmpeg_path: str | None = Field(default=None, description="Custom FFmpeg executable path")
    ffprobe_path: str | None = Field(default=None, description="Custom FFprobe executable path")

    # ── Internal state (not persisted) ──
    _settings_file_path: Path | None = None
    _loaded_from_file: bool = False

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Invalid log level: {v}. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return upper

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization to load settings from file."""
        if not self._loaded_from_file:
            self._merge_from_file()

    def _merge_from_file(self) -> None:
        """Merge settings from the JSON config file."""
        settings_file = self.storage.app_directory / "config" / "settings.json"
        self._settings_file_path = settings_file

        if settings_file.exists():
            try:
                with open(settings_file) as f:
                    file_settings: dict = json.load(f)
                self._loaded_from_file = True
                self._apply_dict(file_settings)
            except (json.JSONDecodeError, OSError) as exc:
                import logging

                logging.warning("Failed to load settings file %s: %s", settings_file, exc)

    def _apply_dict(self, data: dict) -> None:
        """Apply a dictionary of settings to the current settings."""
        if "gpu" in data and isinstance(data["gpu"], dict):
            for key, value in data["gpu"].items():
                if hasattr(self.gpu, key):
                    setattr(self.gpu, key, value)
        if "storage" in data and isinstance(data["storage"], dict):
            for key, value in data["storage"].items():
                if hasattr(self.storage, key):
                    setattr(self.storage, key, value)
        if "pipeline" in data and isinstance(data["pipeline"], dict):
            for key, value in data["pipeline"].items():
                if hasattr(self.pipeline, key):
                    setattr(self.pipeline, key, value)
        if "export" in data and isinstance(data["export"], dict):
            for key, value in data["export"].items():
                if hasattr(self.export, key):
                    setattr(self.export, key, value)
        if "auto_save" in data and isinstance(data["auto_save"], dict):
            for key, value in data["auto_save"].items():
                if hasattr(self.auto_save, key):
                    setattr(self.auto_save, key, value)
        # Top-level overrides
        for key in ("host", "port", "debug", "log_level", "celery_broker_url", "celery_worker_count"):
            if key in data:
                setattr(self, key, data[key])

    def to_dict(self) -> dict:
        """Export settings as a JSON-serializable dictionary."""
        return json.loads(self.model_dump_json())

    def save(self) -> None:
        """Save current settings to the JSON config file."""
        path = self._settings_file_path or (self.storage.app_directory / "config" / "settings.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @property
    def storage_path(self) -> Path:
        """Convenience accessor for the storage directory."""
        return self.storage.app_directory


def get_settings() -> Settings:
    """
    Return the global settings singleton.

    Creates the singleton on first call. Subsequent calls return the
    existing instance for consistency across the application.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Force-reload settings from file. Used after settings changes."""
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance
