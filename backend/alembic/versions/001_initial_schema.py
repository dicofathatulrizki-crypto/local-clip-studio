"""Initial schema for Local Clip Studio v1.0.0

Creates all 12 tables for the application:
- projects (with soft-delete support)
- video_master (deduplicated video storage)
- project_videos (join table)
- analyses (AI pipeline results)
- clip_candidates (AI-generated clip suggestions)
- timeline_states (timeline editing state)
- export_jobs (video export tracking)
- caption_tracks (subtitle/caption data)
- processing_queue (background job tracking)
- version_snapshots (project version history)
- settings (global key-value config)
- provider_configs (AI provider configuration)
- model_registry (AI model file tracking)

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Projects ───────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_opened_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("is_archived", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    # ── Video Master ───────────────────────────────────────────
    op.create_table(
        "video_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("video_codec", sa.String(50), nullable=False),
        sa.Column("audio_codec", sa.String(50), nullable=True),
        sa.Column("audio_channels", sa.Integer(), nullable=True),
        sa.Column("audio_sample_rate", sa.Integer(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── Project Videos (join table) ────────────────────────────
    op.create_table(
        "project_videos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("video_id", sa.String(36),
                  sa.ForeignKey("video_master.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("import_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("proxy_path", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "video_id", name="uq_project_video"),
    )

    # ── Analyses ───────────────────────────────────────────────
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("video_id", sa.String(36),
                  sa.ForeignKey("project_videos.id", ondelete="CASCADE"),
                  nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("transcript", sa.JSON(), nullable=True),
        sa.Column("speakers", sa.JSON(), nullable=True),
        sa.Column("scenes", sa.JSON(), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("emotions", sa.JSON(), nullable=True),
        sa.Column("hooks", sa.JSON(), nullable=True),
        sa.Column("chapters", sa.JSON(), nullable=True),
        sa.Column("silences", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("quality_details", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pipeline_version", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("video_id", name="uq_analysis_video"),
    )

    # ── Clip Candidates ────────────────────────────────────────
    op.create_table(
        "clip_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("video_id", sa.String(36),
                  sa.ForeignKey("project_videos.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("virality_score", sa.Integer(), nullable=True),
        sa.Column("hook_score", sa.Integer(), nullable=True),
        sa.Column("content_density", sa.Float(), nullable=True),
        sa.Column("audio_clarity", sa.Float(), nullable=True),
        sa.Column("visual_variety", sa.Float(), nullable=True),
        sa.Column("engagement_score", sa.Float(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate", index=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Index("idx_clip_video_status", "video_id", "status"),
        sa.Index("idx_clip_video_rank", "video_id", "rank"),
    )

    # ── Timeline States ────────────────────────────────────────
    op.create_table(
        "timeline_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("tracks", sa.JSON(), nullable=False),
        sa.Column("markers", sa.JSON(), nullable=False),
        sa.Column("zoom_level", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("playhead_position_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_timeline_project"),
    )

    # ── Export Jobs ────────────────────────────────────────────
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clip_id", sa.String(36),
                  sa.ForeignKey("clip_candidates.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("preset", sa.String(50), nullable=True),
        sa.Column("resolution", sa.String(20), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("include_captions", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("caption_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("encoding_speed", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Index("idx_export_status", "status"),
    )

    # ── Caption Tracks ─────────────────────────────────────────
    op.create_table(
        "caption_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clip_id", sa.String(36),
                  sa.ForeignKey("clip_candidates.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("style", sa.JSON(), nullable=True),
        sa.Column("captions", sa.JSON(), nullable=False),
        sa.Column("is_source_language", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_auto_generated", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("clip_id", "language", name="uq_clip_language"),
    )

    # ── Processing Queue ───────────────────────────────────────
    op.create_table(
        "processing_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("video_id", sa.String(36),
                  sa.ForeignKey("project_videos.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Index("idx_queue_status_priority", "status", "priority"),
    )

    # ── Version Snapshots ──────────────────────────────────────
    op.create_table(
        "version_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_path", sa.Text(), nullable=False),
        sa.Column("snapshot_type", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "version_number", name="uq_snapshot_version"),
    )

    # ── Settings ───────────────────────────────────────────────
    op.create_table(
        "settings",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── Provider Configs ───────────────────────────────────────
    op.create_table(
        "provider_configs",
        sa.Column("provider_id", sa.String(50), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("task_routing", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── Model Registry ─────────────────────────────────────────
    op.create_table(
        "model_registry",
        sa.Column("model_id", sa.String(100), primary_key=True),
        sa.Column("model_type", sa.String(30), nullable=False),
        sa.Column("size_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vram_mb", sa.Integer(), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_downloaded"),
        sa.Column("download_progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("model_registry")
    op.drop_table("provider_configs")
    op.drop_table("settings")
    op.drop_table("version_snapshots")
    op.drop_table("processing_queue")
    op.drop_table("caption_tracks")
    op.drop_table("export_jobs")
    op.drop_table("timeline_states")
    op.drop_table("clip_candidates")
    op.drop_table("analyses")
    op.drop_table("project_videos")
    op.drop_table("video_master")
    op.drop_table("projects")
