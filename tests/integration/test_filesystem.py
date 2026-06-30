"""Integration tests for the filesystem storage subsystem.

Tests end-to-end flows across multiple storage managers:
- Directory + File pipeline
- Storage lifecycle (create → store → verify → cleanup)
- CleanupScheduler lifecycle
- Backup create → list → verify → restore
- Cross-manager interactions
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

from backend.infrastructure.filesystem.backup_manager import BackupManager
from backend.infrastructure.filesystem.cache_manager import CacheManager
from backend.infrastructure.filesystem.cleanup_scheduler import CleanupScheduler
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.export_manager import ExportStorageManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.filesystem.model_manager import ModelStorageManager
from backend.infrastructure.filesystem.proxy_manager import ProxyStorageManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.filesystem.temp_manager import TemporaryStorageManager


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def temp_base(tmp_path: Path) -> Path:
    """Create a clean temp base directory for each test."""
    base = tmp_path / "localclip_test"
    base.mkdir(parents=True, exist_ok=True)
    return base


# ─── Directory + File Pipeline ──────────────────────────────────


class TestDirectoryFilePipeline:
    """End-to-end directory creation + file operations pipeline."""

    def test_ensure_then_write_then_read(self, temp_base: Path) -> None:
        """Create directory structure, write files atomically, read them back."""
        dm = DirectoryManager(str(temp_base))
        dm.ensure_directories()

        # Verify all standard directories exist
        for subdir in DirectoryManager.SUBDIRECTORIES:
            assert (temp_base / subdir).is_dir()

        # Write a file to the config directory
        config_file = temp_base / "config" / "test_settings.json"
        test_data = json.dumps({"key": "value", "enabled": True})
        FileManager.atomic_write(config_file, test_data)

        # Read it back and verify
        assert config_file.read_text() == test_data

        # Compute and verify hash
        hash_val = FileManager.compute_hash(config_file)
        assert FileManager.verify_hash(config_file, hash_val)

    def test_project_directory_with_files(self, temp_base: Path) -> None:
        """Create project directories, write files, list them, delete."""
        dm = DirectoryManager(str(temp_base))
        pid = str(uuid.uuid4())

        # Create project directory structure
        dirs = dm.ensure_project_dirs(pid)
        for key, path in dirs.items():
            assert path.is_dir(), f"Missing: {key}"

        # Write source file
        src = dirs["sources"] / "video.mp4"
        FileManager.atomic_write(src, b"fake video content")

        # Write proxy file
        proxy = dirs["proxies"] / "video_720p.mp4"
        FileManager.atomic_write(proxy, b"fake proxy content")

        # List sources
        files = FileManager.list_files(dirs["sources"], "*")
        assert len(files) == 1

        # Copy from sources to cache
        cache_path = dirs["cache_frames"] / "frame_001.jpg"
        FileManager.safe_copy(src, cache_path)
        assert cache_path.exists()
        assert FileManager.verify_hash(cache_path, FileManager.compute_hash(src))


# ─── Storage Manager Integration ────────────────────────────────


class TestStorageManagerIntegration:
    """Integration tests for storage monitoring and quotas."""

    def test_disk_space_real_directory(self, temp_base: Path) -> None:
        """Query disk space for a real directory."""
        mgr = StorageManager(str(temp_base))
        space = mgr.get_disk_space(temp_base)

        assert space["total_bytes"] > 0
        assert space["free_bytes"] > 0
        assert space["used_bytes"] >= 0

    def test_usage_with_real_files(self, temp_base: Path) -> None:
        """Usage tracking with actual files."""
        mgr = StorageManager(str(temp_base))
        (temp_base / "cache").mkdir(parents=True)

        # Write a test file
        test_file = temp_base / "cache" / "test.bin"
        test_file.write_bytes(b"x" * 1000)
        (temp_base / "cache" / "sub").mkdir()
        (temp_base / "cache" / "sub" / "nested.bin").write_bytes(b"y" * 500)

        usage = mgr.get_usage("cache")
        assert usage.file_count >= 2
        assert usage.used_bytes >= 1500

    def test_category_path_resolution(self, temp_base: Path) -> None:
        """All storage categories resolve to correct paths."""
        mgr = StorageManager(str(temp_base))

        for cat in ("projects", "cache", "models", "logs", "temp", "exports"):
            (temp_base / cat).mkdir(parents=True)
            usage = mgr.get_usage(cat)
            assert usage.category == cat
            assert cat in usage.path


# ─── Temp File Lifecycle ────────────────────────────────────────


class TestTempFileLifecycle:
    """Integration test for temp file lifecycle."""

    def test_create_expire_cleanup(self, temp_base: Path) -> None:
        """Create temp file, wait for expiration, verify cleanup."""
        # Use 1-hour retention so files older than 1 hour get cleaned up
        mgr = TemporaryStorageManager(str(temp_base), retention_hours=1)
        mgr.ensure_dirs()

        # Create a temp file
        path = mgr.create_temp_path(subdir="processing", suffix=".mp4")

        # Write something to it
        Path(path).write_text("temp data")

        # Set mtime far in the past (2 hours ago) to ensure it's expired
        old_time = time.time() - 7200  # 2 hours ago (retention is 1 hour)
        os.utime(path, (old_time, old_time))

        # Cleanup expired (should remove it since it's 2 hours old, retention 1 hour)
        removed = mgr.cleanup_expired()
        assert removed >= 1
        assert not Path(path).exists()

    def test_register_download_then_clean_all(self, temp_base: Path) -> None:
        """Register download, verify path, then clean all temp files."""
        mgr = TemporaryStorageManager(str(temp_base))
        mgr.ensure_dirs()

        # Register downloads and processing
        d1 = mgr.register_download("https://example.com/video_1.mp4")
        d2 = mgr.register_download("https://example.com/clip.mov")
        p1 = mgr.register_processing("job_123", suffix=".wav")

        # Write content to created paths
        for path in (d1, d2, p1):
            Path(path).write_text("content")

        # Verify usage
        usage = mgr.get_usage()
        assert usage["downloads"]["file_count"] >= 2
        assert usage["processing"]["file_count"] >= 1

        # Clean all
        total = mgr.clean_all()
        assert total >= 3

        # Verify all cleaned
        for path in (d1, d2, p1):
            assert not Path(path).exists()


# ─── Cache + Backup Pipeline ────────────────────────────────────


class TestCacheBackupPipeline:
    """Integration test for cache and backup round-trips."""

    def test_cache_then_backup_then_restore(self, temp_base: Path) -> None:
        """Store in cache, backup project, restore from backup."""
        # Setup managers
        cache = CacheManager(str(temp_base))
        backup = BackupManager(str(temp_base))

        # Ensure directories exist
        cache.ensure_dirs()
        pid = str(uuid.uuid4())

        # 1. Store something in cache
        cache.set("frames", "shot_001.jpg", b"frame_data_123")
        assert cache.get("frames", "shot_001.jpg") == b"frame_data_123"

        # 2. Create project snapshot
        project_data = {
            "name": "Test Project",
            "cache_keys": ["shot_001.jpg", "shot_002.jpg"],
            "settings": {"resolution": "1080p"},
        }
        snapshot_path = backup.create_snapshot(pid, project_data, snapshot_type="manual")
        assert Path(snapshot_path).exists()

        # 3. List and verify snapshots
        snapshots = backup.list_snapshots(pid)
        assert len(snapshots) == 1
        assert snapshots[0]["version"] == 1
        assert snapshots[0]["type"] == "manual"

        # 4. Verify snapshot integrity
        assert backup.verify_snapshot(pid, 1) is True

        # 5. Restore from snapshot
        restored = backup.restore_snapshot(pid, 1)
        assert restored is not None
        assert restored["name"] == "Test Project"
        assert restored["settings"]["resolution"] == "1080p"

        # 6. Delete snapshot and verify
        assert backup.delete_snapshot(pid, 1) is True
        assert len(backup.list_snapshots(pid)) == 0

    def test_multiple_snapshots_with_retention(self, temp_base: Path) -> None:
        """Create multiple snapshots and verify retention enforcement."""
        backup = BackupManager(str(temp_base), max_backups=3)
        pid = str(uuid.uuid4())

        # Create 5 snapshots
        for i in range(5):
            backup.create_snapshot(pid, {"index": i}, snapshot_type="auto")

        # Verify only 3 remain (retention limit)
        snapshots = backup.list_snapshots(pid)
        assert len(snapshots) == 3

        # Snapshot version numbers increase monotonically
        sorted_by_mtime = sorted(snapshots, key=lambda s: s["created_at"], reverse=True)
        # Latest snapshot should have the highest version number
        for i in range(1, len(sorted_by_mtime)):
            assert sorted_by_mtime[i - 1]["version"] > sorted_by_mtime[i]["version"]


# ─── Proxy + Export Pipeline ────────────────────────────────────


class TestProxyExportPipeline:
    """Integration test for proxy and export managers."""

    def test_proxy_then_export(self, temp_base: Path) -> None:
        """Create proxy file, then export, verify paths and naming."""
        proxy = ProxyStorageManager(str(temp_base))
        export = ExportStorageManager(str(temp_base))
        pid = str(uuid.uuid4())

        # Create a source file (simulate video)
        (temp_base / "projects" / pid / "proxies").mkdir(parents=True)

        # Get proxy path
        proxy_file = proxy.proxy_path(pid, "abc123", height=720)
        proxy_file.write_text("fake proxy data")
        assert proxy_file.exists()

        # Check existing proxy
        existing = proxy.get_existing_proxy(pid, "abc123")
        assert existing is not None
        assert "720p" in str(existing)

        # Create export
        export_path = export.export_path(pid, "My Clip", "mp4")
        export_path.write_text("fake export")
        assert export_path.exists()

        # Verify export name format
        assert export_path.stem.startswith("my_clip_")
        assert export_path.suffix == ".mp4"

        # List project exports
        exports = export.list_project_exports(pid)
        assert len(exports) == 1

    def test_global_exports(self, temp_base: Path) -> None:
        """Global exports directory works and aggregates correctly."""
        export = ExportStorageManager(str(temp_base))
        pid = str(uuid.uuid4())

        # Create both project and global exports
        project_path = export.export_path(pid, "Project Clip", "mp4", use_global=False)
        global_path = export.export_path(pid, "Global Clip", "webm", use_global=True)

        project_path.parent.mkdir(parents=True, exist_ok=True)
        global_path.parent.mkdir(parents=True, exist_ok=True)
        project_path.write_text("project export")
        global_path.write_text("global export")

        # Verify both exist
        assert project_path.exists()
        assert global_path.exists()

        # Get usage (aggregated)
        usage = export.get_usage()
        assert usage["file_count"] >= 2


# ─── CleanupScheduler Lifecycle ─────────────────────────────────


class TestCleanupSchedulerLifecycle:
    """Integration test for CleanupScheduler lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, temp_base: Path) -> None:
        """Start, run cleanup, stop the scheduler."""
        scheduler = CleanupScheduler(str(temp_base))

        assert scheduler.is_running is False

        # Start scheduler
        await scheduler.start()
        assert scheduler.is_running is True

        # Run cleanup
        results = await scheduler.run_cleanup()
        assert "temp_files_removed" in results
        assert "cache_entries_removed" in results
        assert "storage_limit_exceeded" in results
        assert "log_rotation" in results

        # Stop scheduler
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_cleanup_with_data(self, temp_base: Path) -> None:
        """Create temporary files and cache entries, then run cleanup."""
        scheduler = CleanupScheduler(str(temp_base))

        # Create temp files
        temp_mgr = TemporaryStorageManager(str(temp_base), retention_hours=0)
        temp_mgr.ensure_dirs()
        old_path = temp_mgr.create_temp_path(subdir="downloads", suffix=".mp4")
        Path(old_path).write_text("old temp file")
        # Set mtime far in the past
        os.utime(old_path, (100, 100))

        # Create cache entries
        cache = CacheManager(str(temp_base))
        cache.ensure_dirs()
        cache.set("frames", "old_frame.jpg", b"old_frame_data")

        # Run cleanup
        results = await scheduler.run_cleanup()

        # Temp files should be removed
        assert results["temp_files_removed"] >= 1
        assert not Path(old_path).exists()

        # Cache cleanup should run without error
        assert isinstance(results["cache_entries_removed"], dict)


# ─── Model + Proxy + Export Integration ─────────────────────────


class TestModelStorageIntegration:
    """Integration test for model storage operations."""

    def test_model_download_and_verify(self, temp_base: Path) -> None:
        """Simulate model download, verify integrity."""
        model = ModelStorageManager(str(temp_base))
        model.ensure_dirs()

        # Simulate downloading a model
        cat = "whisper"
        model_id = "large-v3"
        model_dir = model.model_path(cat, model_id)
        model_dir.mkdir(parents=True, exist_ok=True)

        model_file = model_dir / "model.pt"
        model_file.write_text("fake model weights data")

        # List models
        models = model.list_models(category=cat)
        matching = [m for m in models if m["model_id"] == model_id]
        assert len(matching) == 1
        assert matching[0]["size_bytes"] > 0

        # Verify integrity
        hash_val = FileManager.compute_hash(model_file)
        assert model.verify_integrity(cat, model_id, hash_val) is True

        # Modify and check integrity fails
        model_file.write_text("corrupted data")
        assert model.verify_integrity(cat, model_id, hash_val) is False

    def test_cross_category_listing(self, temp_base: Path) -> None:
        """List models across multiple categories."""
        model = ModelStorageManager(str(temp_base))
        model.ensure_dirs()

        # Create models in different categories
        for cat in ("whisper", "yolo", "llm"):
            model_dir = model.model_path(cat, f"{cat}_v1")
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "model.bin").write_text("data")

        # List all models
        all_models = model.list_models()
        assert len(all_models) == 3

        # List by category
        whisper_models = model.list_models(category="whisper")
        assert len(whisper_models) == 1
