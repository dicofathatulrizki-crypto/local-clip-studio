"""
Default configuration values for Local Clip Studio.

These values are merged with user settings from settings.json.
User-provided values always take precedence.
"""

from pathlib import Path

# ─── Application Identity ────────────────────────────────────────────────
APP_NAME: str = "Local Clip Studio"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = "Local-first AI-powered video clipping application"

# ─── Server Defaults ─────────────────────────────────────────────────────
DEFAULT_HOST: str = "127.0.0.1"  # localhost only for security
DEFAULT_PORT: int = 8765
DEFAULT_FRONTEND_PORT: int = 5173

# ─── Storage ──────────────────────────────────────────────────────────────
DEFAULT_STORAGE_PATH: Path = Path.home() / ".localclip"
DEFAULT_MAX_PROJECT_SIZE_GB: int = 200
DEFAULT_MAX_CACHE_SIZE_GB: int = 50
DEFAULT_MAX_MODEL_STORAGE_GB: int = 100
DEFAULT_MAX_LOG_SIZE_MB: int = 500
DEFAULT_MAX_TEMP_SIZE_GB: int = 20
DEFAULT_MAX_FILE_SIZE_GB: int = 50

# ─── Auto-Cleanup ────────────────────────────────────────────────────────
DEFAULT_CLEANUP_ENABLED: bool = True
DEFAULT_CLEANUP_INTERVAL_HOURS: int = 24
DEFAULT_TEMP_RETENTION_HOURS: int = 24
DEFAULT_CACHE_RETENTION_DAYS: int = 7
DEFAULT_LOG_RETENTION_DAYS: int = 30

# ─── GPU / Hardware ──────────────────────────────────────────────────────
DEFAULT_GPU_BACKEND: str = "auto"  # auto, cuda, mps, rocm, cpu
DEFAULT_GPU_MEMORY_LIMIT_PERCENT: int = 80
DEFAULT_ENABLE_CPU_FALLBACK: bool = True

# ─── AI Pipeline ─────────────────────────────────────────────────────────
DEFAULT_STT_MODEL: str = "large-v3"
DEFAULT_PIPELINE_TIMEOUT_MINUTES: int = 30
DEFAULT_MAX_CONCURRENT_JOBS: int = 2
DEFAULT_MAX_PLUGIN_MEMORY_MB: int = 4096

# ─── Export ──────────────────────────────────────────────────────────────
DEFAULT_EXPORT_FORMAT: str = "mp4"
DEFAULT_EXPORT_PRESET: str = "standard"
DEFAULT_EXPORT_GPU_ENCODING: bool = True

# ─── Logging ─────────────────────────────────────────────────────────────
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_LOG_FORMAT: str = "json"  # json or console

# ─── Auto-Save ───────────────────────────────────────────────────────────
DEFAULT_AUTO_SAVE_INTERVAL_SECONDS: int = 60
DEFAULT_VERSION_HISTORY_COUNT: int = 10

# ─── Celery ──────────────────────────────────────────────────────────────
DEFAULT_CELERY_BROKER_URL: str = "filesystem://"
DEFAULT_CELERY_WORKER_COUNT: int = 4
