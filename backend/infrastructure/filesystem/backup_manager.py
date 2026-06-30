"""
BackupManager — manages project backups, version history, and restore.

Creates point-in-time snapshots of project state, manages version
retention, and provides integrity verification for backups.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class BackupManager:
    """Manages project backups and version history.

    Backups are stored per-project under projects/{project_id}/versions/.
    Supports automatic snapshots (on close, pre-analysis, pre-export)
    and manual snapshots initiated by the user.

    Retention: maximum 10 backups per project (configurable).
    """

    DEFAULT_MAX_BACKUPS = 10
    SNAPSHOT_TYPES = ("auto", "manual", "pre_export", "pre_analysis")

    def __init__(
        self,
        base_path: str | Path | None = None,
        max_backups: int = DEFAULT_MAX_BACKUPS,
    ) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

        self._max_backups = max_backups
        self._dir_manager = DirectoryManager(str(self._base))

    def versions_dir(self, project_id: str) -> Path:
        """Get the versions directory for a project.

        Args:
            project_id: UUID of the project
        Returns:
            Path to versions directory
        """
        return self._dir_manager.project_dir(project_id) / "versions"

    def create_snapshot(
        self,
        project_id: str,
        data: dict[str, Any],
        snapshot_type: str = "auto",
        description: str | None = None,
    ) -> Path:
        """Create a point-in-time snapshot of a project's state.

        Args:
            project_id: UUID of the project
            data: Project state data to snapshot (serializable dict)
            snapshot_type: Type of snapshot (auto, manual, pre_export, pre_analysis)
            description: Optional user-provided description
        Returns:
            Path to the created snapshot file
        Raises:
            ValueError: If snapshot_type is invalid
        """
        if snapshot_type not in self.SNAPSHOT_TYPES:
            msg = f"Invalid snapshot type: {snapshot_type}. Valid: {self.SNAPSHOT_TYPES}"
            raise ValueError(msg)

        version_dir = self.versions_dir(project_id)
        version_dir.mkdir(parents=True, exist_ok=True)

        # Determine version number (monotonically increasing)
        existing = self.list_snapshots(project_id)
        max_version = max((s.get("version", 0) for s in existing), default=0)
        version_number = max_version + 1

        unique_id = uuid.uuid4().hex[:8]
        filename = f"v_{snapshot_type}_{unique_id}.json"
        snapshot_path = version_dir / filename

        # Compute checksum of the data (before serializing the full snapshot
        # which includes the checksum itself)
        data_json = json.dumps(data, default=str, sort_keys=True)
        checksum = hashlib.sha256(data_json.encode()).hexdigest()

        # Build snapshot content with checksum
        snapshot = {
            "version": version_number,
            "type": snapshot_type,
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "description": description or f"{snapshot_type} snapshot v{version_number}",
            "data": data,
            "checksum": checksum,
        }

        # Write snapshot atomically
        content = json.dumps(snapshot, indent=2, default=str)
        FileManager.atomic_write(snapshot_path, content)

        # Enforce retention limit
        self._enforce_retention(project_id)

        logger.info(
            "Created project snapshot",
            extra={
                "project_id": project_id,
                "version": version_number,
                "type": snapshot_type,
            },
        )

        return snapshot_path

    def list_snapshots(self, project_id: str) -> list[dict[str, Any]]:
        """List all snapshots for a project, sorted newest first.

        Args:
            project_id: UUID of the project
        Returns:
            List of snapshot metadata dicts
        """
        version_dir = self.versions_dir(project_id)
        if not version_dir.exists():
            return []

        snapshots = []
        for item in sorted(version_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if item.suffix == ".json":
                try:
                    data = json.loads(item.read_text())
                    snapshots.append({
                        "path": str(item),
                        "filename": item.name,
                        "version": data.get("version", 0),
                        "type": data.get("type", "unknown"),
                        "created_at": data.get("created_at", ""),
                        "description": data.get("description", ""),
                        "file_size_bytes": item.stat().st_size,
                        "checksum": data.get("checksum", ""),
                    })
                except (json.JSONDecodeError, OSError):
                    continue

        return snapshots

    def get_snapshot(self, project_id: str, version: int) -> dict[str, Any] | None:
        """Get a specific snapshot by version number.

        Args:
            project_id: UUID of the project
            version: Version number
        Returns:
            Snapshot data dict or None
        """
        for snap in self.list_snapshots(project_id):
            if snap["version"] == version:
                path = Path(snap["path"])
                try:
                    result: dict[str, Any] = json.loads(path.read_text())
                    return result
                except (json.JSONDecodeError, OSError):
                    return None
        return None

    def restore_snapshot(self, project_id: str, version: int) -> dict[str, Any] | None:
        """Restore a project from a specific snapshot version.

        Args:
            project_id: UUID of the project
            version: Version number to restore
        Returns:
            The snapshot data dict (the project state to restore), or None
        """
        snapshot = self.get_snapshot(project_id, version)
        if snapshot is None:
            logger.warning(
                "Snapshot not found for restore",
                extra={"project_id": project_id, "version": version},
            )
            return None

        logger.info(
            "Restored project from snapshot",
            extra={
                "project_id": project_id,
                "version": version,
                "type": snapshot.get("type"),
            },
        )
        return snapshot.get("data")

    def delete_snapshot(self, project_id: str, version: int) -> bool:
        """Delete a specific snapshot.

        Args:
            project_id: UUID of the project
            version: Version number to delete
        Returns:
            True if deleted
        """
        for snap in self.list_snapshots(project_id):
            if snap["version"] == version:
                return FileManager.safe_delete(snap["path"])
        return False

    def verify_snapshot(self, project_id: str, version: int) -> bool:
        """Verify the integrity of a snapshot by checking its checksum.

        Computes the checksum of the data field and compares it
        against the stored checksum value.

        Args:
            project_id: UUID of the project
            version: Version number
        Returns:
            True if checksum matches
        """
        for snap in self.list_snapshots(project_id):
            if snap["version"] == version:
                path = Path(snap["path"])
                try:
                    data = json.loads(path.read_text())
                except (json.JSONDecodeError, OSError):
                    return False
                expected = data.get("checksum", "")
                if not expected:
                    return False
                # Recompute checksum from the stored data
                stored_data = data.get("data", {})
                data_json = json.dumps(stored_data, default=str, sort_keys=True)
                actual = hashlib.sha256(data_json.encode()).hexdigest()
                return actual == expected  # type: ignore[no-any-return]
        return False

    def get_usage(self, project_id: str | None = None) -> dict[str, object]:
        """Get backup storage usage.

        Args:
            project_id: Optional project ID to scope usage
        Returns:
            Dict with size_bytes, count, max_backups
        """
        if project_id:
            version_dir = self.versions_dir(project_id)
            return {
                "size_bytes": FileManager.get_size(version_dir),
                "snapshot_count": len(self.list_snapshots(project_id)),
                "max_backups": self._max_backups,
            }

        # Aggregate across all projects
        projects_dir = self._base / "projects"
        total_size = 0
        total_count = 0
        if projects_dir.exists():
            for proj_dir in projects_dir.iterdir():
                if proj_dir.is_dir():
                    version_dir = proj_dir / "versions"
                    total_size += FileManager.get_size(version_dir)
                    total_count += len(self.list_snapshots(proj_dir.name))

        return {
            "size_bytes": total_size,
            "snapshot_count": total_count,
            "max_backups": self._max_backups,
        }

    # ─── Private ─────────────────────────────────────────────────

    def _enforce_retention(self, project_id: str) -> None:
        """Remove oldest snapshots if over the retention limit."""
        snapshots = self.list_snapshots(project_id)
        if len(snapshots) <= self._max_backups:
            return

        # Remove oldest (already sorted newest-first, so take from end)
        to_remove = snapshots[self._max_backups:]
        for snap in to_remove:
            FileManager.safe_delete(snap["path"])
            logger.debug(
                "Removed old snapshot",
                extra={
                    "project_id": project_id,
                    "version": snap["version"],
                    "filename": snap["filename"],
                },
            )
