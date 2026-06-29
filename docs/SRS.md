# Local Clip Studio — Software Requirements Specification

> **Status:** DRAFT  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Classification:** Technical Specification  
> **Traceability:** Vision Document v2.0 → PRD v1.0 → SRS v1.0

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Hardware Abstraction Layer](#3-hardware-abstraction-layer)
4. [Storage Layout & Filesystem](#4-storage-layout--filesystem)
5. [Database Design](#5-database-design)
6. [API Specification](#6-api-specification)
7. [WebSocket Specification](#7-websocket-specification)
8. [AI Pipeline Specification](#8-ai-pipeline-specification)
9. [Plugin Architecture](#9-plugin-architecture)
10. [Service Contracts](#10-service-contracts)
11. [State Machines](#11-state-machines)
12. [Error Catalog](#12-error-catalog)
13. [Testing Specification](#13-testing-specification)
14. [Security Specification](#14-security-specification)
15. [Non-Functional Requirements](#15-non-functional-requirements)
16. [Traceability Matrix](#16-traceability-matrix)
17. [Explicitly Excluded Scope](#17-explicitly-excluded-scope)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the complete technical specification for Local Clip Studio — a local-first, AI-powered video editing application. This document translates the approved Product Requirements (PRD v1.0) into precise, implementable engineering specifications.

### 1.2 Scope

This SRS covers all backend services, API contracts, database schema, AI pipeline stages, plugin interfaces, state machines, error handling, testing requirements, and deployment specifications for v1.0 of Local Clip Studio.

### 1.3 Document Conventions

| Convention | Meaning |
|------------|---------|
| `REQ-SRS-{NNN}` | Unique requirement identifier |
| `[P0]` | Priority: Must implement for MVP |
| `[P1]` | Priority: Should implement for v1.0 |
| `[P2]` | Priority: Could implement, deferred |
| `**bold**` | Key technical terms or constraints |
| `monospace` | Code, endpoints, schemas, file paths |

### 1.4 Traceability

Every requirement traces upward: `REQ-SRS-XXX → PRD-YYY-XXX → VIS-§N`

### 1.5 Terminology

| Term | Definition |
|------|------------|
| **HAL** | Hardware Abstraction Layer |
| **STT** | Speech-to-Text |
| **LLM** | Large Language Model |
| **HAL-backend** | Concrete implementation of a HAL (CUDA, MPS, ROCm, CPU) |
| **Plugin** | Dynamically loaded module implementing a formal interface |
| **Job** | A unit of work processed by the AI pipeline |
| **Proxy** | Lower-resolution video copy used for timeline editing |
| **Keyframe** | Control point defining a property value at a specific time |

---

## 2. System Overview

### 2.1 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         BROWSER (React SPA)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐   │
│  │ Workspace│  │ Timeline │  │ Media    │  │ Settings       │   │
│  │ (Panels) │  │ (Canvas) │  │ Browser  │  │ (Config UI)    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘   │
│       └──────────────┴─────────────┴────────────────┘           │
│                              │                                   │
│                    HTTP REST + WebSocket                         │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                    FASTAPI APPLICATION SERVER                     │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    API Gateway Layer                      │   │
│  │  /api/v1/projects  /api/v1/settings  /api/v1/models      │   │
│  │  /api/v1/providers /api/v1/ws (WebSocket upgrade)        │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Service Layer                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │Project   │ │Import    │ │Pipeline  │ │Export      │  │   │
│  │  │Service   │ │Service   │ │Service   │ │Service     │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │Provider  │ │Plugin    │ │Settings  │ │Analytics   │  │   │
│  │  │Service   │ │Service   │ │Service   │ │Service     │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Domain Layer                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │Project   │ │Video     │ │Clip      │ │Transcript  │  │   │
│  │  │Aggregate │ │Entity    │ │Entity    │ │Entity      │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               Infrastructure Layer                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │Database  │ │FileSystem│ │HAL       │ │Queue       │  │   │
│  │  │(SQLAlch) │ │(fsspec)  │ │(GPU Abst)│ │(Celery)    │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Version Constraint |
|-------|-----------|-------------------|
| **Frontend** | React 19, TypeScript 5.9, Vite 7 | Locked |
| **UI** | shadcn/ui, Tailwind CSS 4, Framer Motion 12 | Locked |
| **Backend** | Python 3.11+ | ≥ 3.11, < 3.13 |
| **API Framework** | FastAPI | ≥ 0.110 |
| **ORM** | SQLAlchemy 2.0 | ≥ 2.0 |
| **Migrations** | Alembic | ≥ 1.13 |
| **Database** | SQLite (default), PostgreSQL (optional) | SQLite ≥ 3.40 |
| **Task Queue** | Celery | ≥ 5.3 |
| **Message Broker** | Redis (optional), filesystem (default) | Redis ≥ 7.0 |
| **Video Processing** | FFmpeg (system-installed) | ≥ 6.0 |
| **AI Runtime** | PyTorch 2.x, ONNX Runtime | PyTorch ≥ 2.1 |
| **STT** | WhisperX / faster-whisper | Latest |
| **Face Detection** | YOLOv8 (Ultralytics) | ≥ 8.0 |
| **Scene Detection** | PySceneDetect | ≥ 1.0 |
| **LLM Runtime** | llama.cpp (Python bindings) | Latest |

### 2.3 Application Boundaries

| Boundary | Value |
|----------|-------|
| **Entry point** | React SPA served by Vite dev server (dev) or static build (prod) |
| **Backend port** | TCP 8765 (configurable) |
| **Frontend port** | TCP 5173 (dev, configurable) |
| **WebSocket endpoint** | `ws://localhost:8765/api/v1/ws` |
| **Max upload size** | 50 GB (configurable) |
| **Max concurrent jobs** | 2 (configurable) |
| **Max plugin memory** | 4 GB (configurable) |

---

## 3. Hardware Abstraction Layer

### 3.1 Architecture

`REQ-SRS-HAL-001`: All hardware-accelerated computation MUST go through the Hardware Abstraction Layer (HAL). No service may directly reference CUDA, MPS, ROCm, or device-specific APIs. [P0]

`REQ-SRS-HAL-002`: The HAL MUST auto-detect available backends on application startup in priority order: CUDA → MPS → ROCm → CPU. [P0]

`REQ-SRS-HAL-003`: The HAL MUST report backend availability, device name, VRAM total, VRAM available, compute capability, and driver version. [P0]

### 3.2 HAL Interface

```python
# srs/hal/interface.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class HALBackendType(Enum):
    CUDA = "cuda"
    MPS = "mps"
    ROCM = "rocm"
    CPU = "cpu"

@dataclass
class HALDeviceInfo:
    backend: HALBackendType
    device_name: str
    vram_total_bytes: int
    vram_available_bytes: int
    compute_capability: tuple[int, int] | None  # (major, minor) for CUDA
    driver_version: str
    is_available: bool

@dataclass
class HALMemoryBudget:
    recommended_bytes: int
    max_allocatable_bytes: int
    reserved_bytes: int  # VRAM to reserve for system stability

class HALProvider(ABC):
    """Abstract base for HAL backend implementations."""

    @abstractmethod
    def initialize(self, memory_limit_mb: int | None = None) -> None:
        """Initialize the hardware backend. Must be called before any compute."""
        ...

    @abstractmethod
    def get_device_info(self) -> HALDeviceInfo:
        """Return detailed device information."""
        ...

    @abstractmethod
    def get_device(self) -> str:
        """Return device identifier string (e.g., 'cuda:0', 'mps', 'cpu')."""
        ...

    @abstractmethod
    def to_device(self, tensor: "torch.Tensor") -> "torch.Tensor":
        """Move a tensor to the appropriate device."""
        ...

    @abstractmethod
    def get_optimal_batch_size(self, model_size_mb: int, available_memory_mb: int | None = None) -> int:
        """Calculate optimal batch size based on available memory and model size."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release all device resources."""
        ...

    @abstractmethod
    def memory_cleanup(self) -> None:
        """Free cached memory (torch.cuda.empty_cache, etc.)."""
        ...


class HALRegistry:
    """Singleton registry for HAL backends."""

    def register(self, backend: HALBackendType, provider: HALProvider) -> None: ...
    def get_active_backend(self) -> HALProvider: ...
    def get_available_backends(self) -> list[HALProvider]: ...
    def select_best_backend(self) -> HALProvider: ...
```

### 3.3 Backend Implementations

| Backend | Class | Detection Method |
|---------|-------|-----------------|
| CUDA | `CUDAProvider` | `torch.cuda.is_available()` |
| MPS | `MPSProvider` | `torch.backends.mps.is_available()` |
| ROCm | `ROCmProvider` | `torch.cuda.is_available() and torch.version.hip is not None` |
| CPU | `CPUProvider` | Always available (fallback) |

### 3.4 Memory Management

`REQ-SRS-HAL-004`: The HAL MUST reserve a configurable percentage of VRAM (default: 80%) for application use, leaving headroom for system processes. [P0]

`REQ-SRS-HAL-005`: The HAL MUST enforce a hard memory limit per model, preventing OOM by falling back to CPU for oversized models. [P1]

`REQ-SRS-HAL-006`: The HAL MUST support per-model memory quotas for multi-model concurrent execution. [P2]

### 3.5 HAL Usage Contract

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Service    │────▶│   HAL Registry  │────▶│   HALProvider   │
│ (Pipeline Stage)│     │  (get_active)   │     │  (CUDA/MPS/CPU) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                              │
        │  "move to device"                            │  torch.to(device)
        │  "optimal batch size"                        │  vram check
        │  "memory cleanup"                            │  cache empty
        └──────────────────────────────────────────────┘
```

### 3.6 Backend Selection Algorithm

```python
def select_best_backend() -> HALProvider:
    candidates = [
        (HALBackendType.CUDA, CUDAProvider()),
        (HALBackendType.MPS, MPSProvider()),
        (HALBackendType.ROCM, ROCMProvider()),
        (HALBackendType.CPU, CPUProvider()),
    ]
    for backend_type, provider in candidates:
        if provider.is_available():
            provider.initialize()
            return provider
    return CPUProvider()
```

---

## 4. Storage Layout & Filesystem

### 4.1 Root Directory

`REQ-SRS-STO-001`: The application root directory SHALL be at `~/.localclip/` on Linux/macOS and `%APPDATA%/LocalClip/` on Windows. Created on first launch. [P0]

### 4.2 Directory Structure

```
~/.localclip/
├── config/
│   ├── settings.json          # User configuration (JSON)
│   ├── providers.json         # Provider config (AES-256 encrypted API keys)
│   └── key.der                # Fernet encryption key (machine-bound)
├── projects/
│   └── {project_uuid}/
│       ├── project.db         # SQLite database for this project
│       ├── project.json       # Project metadata snapshot
│       ├── sources/           # Original imported video files (immutable)
│       │   └── {sha256_prefix}.{ext}   # Named by SHA-256 hash prefix
│       ├── proxies/           # Proxy-encoded videos
│       │   └── {sha256_prefix}_720p.mp4
│       ├── exports/           # Rendered output files
│       │   └── {clip_name}_{timestamp}.{ext}
│       ├── cache/
│       │   ├── frames/        # Extracted video frames (JPEG)
│       │   ├── audio/         # Extracted audio (16kHz mono WAV)
│       │   └── analysis/      # Pipeline analysis results (JSON)
│       ├── thumbnails/        # Thumbnail images
│       └── versions/          # Version history snapshots
│           └── {v_timestamp}.json
├── models/                    # Downloaded AI model files
│   ├── whisper/               # WhisperX model files
│   ├── yolo/                  # YOLOv8 weights
│   ├── sam/                   # SAM model weights
│   ├── llm/                   # Local LLM GGUF files
│   └── embeddings/            # Embedding model files
├── cache/                     # Shared cache
│   ├── frames/                # Extracted frames (global cache)
│   ├── audio/                 # Extracted audio chunks
│   └── thumnails/             # Thumbnail cache
├── logs/
│   ├── app.jsonl              # Application log (JSON lines, rotating)
│   └── pipeline.jsonl         # Pipeline execution log
├── temp/                      # Temporary processing files
│   ├── downloads/             # In-progress downloads
│   └── processing/            # Active pipeline artifacts
├── plugins/                   # User-installed plugins
│   └── {plugin_name}/
│       ├── manifest.json      # Plugin manifest
│       └── plugin.py          # Plugin entry point
└── exports/                   # Default export directory
    └── {project_name}/
        └── {clip_name}.mp4
```

### 4.3 File Naming Conventions

`REQ-SRS-STO-002`: Source files SHALL be named using the first 16 characters of SHA-256 hash: `{hash_prefix}.{ext}`. [P0]

`REQ-SRS-STO-003`: Export files SHALL be named: `{clip_name_slug}_{ISO8601_timestamp}.{ext}`. [P0]

`REQ-SRS-STO-004`: Cache files SHALL include source hash and processing parameters in filename: `{source_hash}_{param_hash}.{ext}`. [P1]

### 4.4 Cleanup Policies

| Directory | Cleanup Trigger | Retention | Action |
|-----------|----------------|-----------|--------|
| `temp/` | Startup + every hour | 24 hours since last access | Delete files |
| `cache/frames/` | On demand or when > 10 GB | 7 days since last access | Delete files |
| `cache/audio/` | On demand or when > 5 GB | 7 days since last access | Delete files |
| `logs/` | On rotation | 30 days, max 500 MB per file | Rotate + archive |
| `projects/*/cache/` | On project close | Project-level | Delete on project delete |
| `models/` | User-initiated | Until user removes | Delete on user request |

`REQ-SRS-STO-005`: Auto-cleanup SHALL run on application startup and every 60 minutes while the application is running. [P1]

`REQ-SRS-STO-006`: Auto-cleanup SHALL NOT delete files that are part of any open project. [P0]

### 4.5 Size Limits

| Category | Default Limit | Configurable |
|----------|--------------|--------------|
| Per-project sources | 200 GB | Yes |
| Global cache | 50 GB | Yes |
| Model storage | 100 GB | Yes |
| Logs | 500 MB | Yes |
| Temp | 20 GB | Yes |
| Per-file import | 50 GB | Yes |

`REQ-SRS-STO-007`: When any limit is exceeded, a warning SHALL be logged and shown in the UI. Import/processing SHALL continue with a warning. [P1]

---

## 5. Database Design

### 5.1 Entity Relationship Diagram

```
┌──────────────────┐       ┌─────────────────────┐
│     Project      │1───N──│    ProjectVideo     │
├──────────────────┤       ├─────────────────────┤
│ id (UUID, PK)    │       │ id (UUID, PK)       │
│ name (TEXT)      │       │ project_id (FK)     │
│ description (TEXT)│      │ video_id (FK)       │
│ created_at (ISO) │       │ import_order (INT)  │
│ updated_at (ISO) │       │ source_path (TEXT)  │
│ last_opened (ISO)│       │ proxy_path (TEXT)   │
│ settings (JSON)  │       │ hash (TEXT, INDEX)  │
│ thumbnail (TEXT) │       │ added_at (ISO)      │
│ version (INT)    │       └─────────┬───────────┘
└──────────────────┘                 │
                                     │N
       ┌─────────────────────────────┘
       │
       │1                 ┌─────────────────────┐
       ├──────────────────│      Analysis       │
       │                  ├─────────────────────┤
       │                  │ id (UUID, PK)       │
       │                  │ video_id (FK, UQ)   │
       │                  │ status (ENUM)       │
       │                  │ transcript (JSON)   │
       │                  │ speakers (JSON)     │
       │                  │ scenes (JSON)       │
       │                  │ topics (JSON)       │
       │                  │ keywords (JSON)     │
       │                  │ emotions (JSON)     │
       │                  │ hooks (JSON)        │
       │                  │ chapters (JSON)     │
       │                  │ quality_score (INT) │
       │                  │ created_at (ISO)    │
       │                  │ duration_ms (INT)   │
       │                  └─────────────────────┘
       │
       │1                 ┌─────────────────────┐
       ├──────────────────│  ClipCandidate      │
       │                  ├─────────────────────┤
       │                  │ id (UUID, PK)       │
       │                  │ video_id (FK)       │
       │                  │ start_ms (INT)      │
       │                  │ end_ms (INT)        │
       │                  │ quality_score (INT) │
       │                  │ virality_score (INT)│
       │                  │ hook_score (INT)    │
       │                  │ title (TEXT)        │
       │                  │ description (TEXT)  │
       │                  │ hashtags (JSON)     │
       │                  │ status (ENUM)       │
       │                  │ created_at (ISO)    │
       │                  │ rank (INT)          │
       │                  └─────────┬───────────┘
       │                            │N
       │1                           │
       ├────────────────────────────┘
       │
       │1                 ┌─────────────────────┐
       └──────────────────│   TimelineState     │
                          ├─────────────────────┤
                          │ id (UUID, PK)       │
                          │ project_id (FK, UQ) │
                          │ tracks (JSON)       │
                          │ markers (JSON)      │
                          │ zoom_level (FLOAT)  │
                          │ playhead_ms (INT)   │
                          │ version (INT)       │
                          │ updated_at (ISO)    │
                          └─────────────────────┘

┌──────────────────┐     ┌─────────────────────┐
│   VideoMaster    │     │     ExportJob       │
├──────────────────┤     ├─────────────────────┤
│ id (UUID, PK)    │     │ id (UUID, PK)       │
│ hash (TEXT, UQ)  │     │ clip_id (FK)        │
│ original_name(TXT)│     │ format (TEXT)       │
│ file_size (INT)  │     │ preset (TEXT)       │
│ duration_ms (INT)│     │ status (ENUM)       │
│ width (INT)      │     │ progress (FLOAT)    │
│ height (INT)     │     │ output_path (TEXT)  │
│ fps (FLOAT)      │     │ error_message (TEXT)│
│ codec (TEXT)     │     │ started_at (ISO)    │
│ audio_codec (TEXT)│     │ completed_at (ISO) │
│ bitrate (INT)    │     │ created_at (ISO)    │
│ storage_path(TEXT)│     └─────────────────────┘
│ imported_at (ISO)│
└──────────────────┘

┌──────────────────┐     ┌─────────────────────┐
│  ProcessingQueue │     │    CaptionTrack     │
├──────────────────┤     ├─────────────────────┤
│ id (UUID, PK)    │     │ id (UUID, PK)       │
│ project_id (FK)  │     │ clip_id (FK)        │
│ video_id (FK)    │     │ language (TEXT)     │
│ job_type (TEXT)  │     │ style (JSON)        │
│ status (ENUM)    │     │ captions (JSON)     │
│ priority (INT)   │     │ is_source (BOOL)    │
│ progress (FLOAT) │     │ created_at (ISO)    │
│ error_msg (TEXT) │     └─────────────────────┘
│ created_at (ISO) │
│ started_at (ISO) │
│ completed_at(ISO)│
└──────────────────┘
```

### 5.2 SQLite Schema (SQLAlchemy 2.0)

```python
# srs/database/schema.py

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum as SAEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import TEXT as SQLITE_TEXT
import enum

class Base(DeclarativeBase):
    pass

# --- Enums ---

class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SCENE_DETECTING = "scene_detecting"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ClipStatus(str, enum.Enum):
    CANDIDATE = "candidate"  # AI-generated suggestion
    ACCEPTED = "accepted"    # User accepted
    REJECTED = "rejected"    # User rejected
    MODIFIED = "modified"    # User manually edited

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExportStatus(str, enum.Enum):
    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# --- Models ---

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    videos = relationship("ProjectVideo", back_populates="project", cascade="all, delete-orphan")
    timeline = relationship("TimelineState", back_populates="project", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_projects_last_opened", "last_opened_at"),
    )


class VideoMaster(Base):
    """Deduplicated video record — shared across projects."""
    __tablename__ = "video_master"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    video_codec: Mapped[str] = mapped_column(String(50), nullable=False)
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectVideo(Base):
    __tablename__ = "project_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("video_master.id"), nullable=False)
    import_order: Mapped[int] = mapped_column(Integer, default=0)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    proxy_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="videos")
    video_master = relationship("VideoMaster")
    analysis = relationship("Analysis", back_populates="video", uselist=False, cascade="all, delete-orphan")
    clip_candidates = relationship("ClipCandidate", back_populates="video", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "video_id", name="uq_project_video"),
        Index("idx_pv_project", "project_id"),
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_videos.id", ondelete="CASCADE"), unique=True)
    status: Mapped[AnalysisStatus] = mapped_column(SAEnum(AnalysisStatus), default=AnalysisStatus.PENDING)
    transcript: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    speakers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scenes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    emotions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hooks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chapters: Mapped[list | None] = mapped_column(JSON, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    video = relationship("ProjectVideo", back_populates="analysis")


class ClipCandidate(Base):
    __tablename__ = "clip_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_videos.id", ondelete="CASCADE"))
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    virality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hook_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ClipStatus] = mapped_column(SAEnum(ClipStatus), default=ClipStatus.CANDIDATE)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    video = relationship("ProjectVideo", back_populates="clip_candidates")

    __table_args__ = (
        Index("idx_clip_video_status", "video_id", "status"),
    )


class TimelineState(Base):
    __tablename__ = "timeline_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    tracks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    zoom_level: Mapped[float] = mapped_column(Float, default=1.0)
    playhead_position_ms: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="timeline")


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String(36), ForeignKey("clip_candidates.id", ondelete="CASCADE"))
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # mp4, mov, webm, srt, etc.
    preset: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ExportStatus] = mapped_column(SAEnum(ExportStatus), default=ExportStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_export_status", "status"),
    )


class ProcessingQueue(Base):
    __tablename__ = "processing_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_videos.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # analysis, export, reframe, etc.
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.QUEUED)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_queue_status", "status", "priority"),
    )


class CaptionTrack(Base):
    __tablename__ = "caption_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String(36), ForeignKey("clip_candidates.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    style: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    captions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_source_language: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("clip_id", "language", name="uq_clip_language"),
    )
```

### 5.3 PostgreSQL Compatibility

`REQ-SRS-DB-001`: All schema definitions MUST use SQLAlchemy's portable type system. The following mappings SHALL be supported:

| SQLite Type | PostgreSQL Type | Migration |
|-------------|----------------|-----------|
| `String` | `VARCHAR` | Automatic |
| `Text` | `TEXT` | Automatic |
| `Integer` | `INTEGER` | Automatic |
| `Float` | `FLOAT` | Automatic |
| `Boolean` | `BOOLEAN` | Automatic |
| `DateTime` | `TIMESTAMP WITH TIME ZONE` | Adjust Alembic type |
| `JSON` | `JSONB` | Adjust Alembic type |
| `Enum` | `ENUM` | Create ENUM type in migration |

`REQ-SRS-DB-002`: All UUID fields SHALL use `uuid.UUID` Python type. SQLite stores as TEXT; PostgreSQL stores as UUID type. [P0]

### 5.4 Migration Strategy

`REQ-SRS-DB-003`: All schema changes SHALL use Alembic migrations. [P0]

`REQ-SRS-DB-004`: Migration files SHALL be stored at `backend/alembic/versions/`. [P0]

`REQ-SRS-DB-005`: Migrations SHALL be auto-generated: `alembic revision --autogenerate -m "description"`. [P0]

`REQ-SRS-DB-006`: Manual review and editing of auto-generated migrations is REQUIRED before committing. [P0]

### 5.5 Backup Strategy

`REQ-SRS-DB-007`: SQLite database SHALL be backed up on project close using `sqlite3_backup()` API. [P1]

`REQ-SRS-DB-008`: Backups SHALL be stored in `{project_dir}/versions/v_{timestamp}.db`. [P1]

`REQ-SRS-DB-009`: Maximum of 10 backups SHALL be retained per project (configurable). [P1]

---

## 6. API Specification

### 6.1 API Conventions

| Convention | Value |
|------------|-------|
| **Base URL** | `http://localhost:8765/api/v1` |
| **Content-Type** | `application/json` |
| **Auth** | None (by design) |
| **Rate Limiting** | None (local application) |
| **CORS** | Allow `http://localhost:5173` (dev), `http://localhost:*` (prod) |
| **Request ID** | `X-Request-ID` header (UUID) — used for correlation tracking |
| **Error format** | `{"error": {"code": "ERR-XXX", "message": "...", "details": {...}}}` |

### 6.2 Endpoint Catalog

#### 6.2.1 Project Endpoints

##### `POST /api/v1/projects` — Create Project

**Request Schema:**
```json
{
  "name": {"type": "string", "minLength": 1, "maxLength": 255, "description": "Project name"},
  "description": {"type": "string", "maxLength": 2000, "nullable": true, "default": null},
  "storage_path": {"type": "string", "nullable": true, "description": "Custom storage path, default: ~/.localclip/projects/{uuid}"}
}
```

**Response Schema (201):**
```json
{
  "id": "uuid-string",
  "name": "My Project",
  "description": null,
  "created_at": "2026-06-29T10:00:00Z",
  "updated_at": "2026-06-29T10:00:00Z",
  "storage_path": "/home/user/.localclip/projects/abc-123",
  "video_count": 0,
  "thumbnail_url": null
}
```

**Status Codes:** `201 Created` | `400 Bad Request` | `500 Internal Server Error`

**Error Codes:** `ERR-VALIDATION-001` (name required) | `ERR-STORAGE-001` (path creation failed)

**Validation Rules:**
- `name`: 1-255 characters, not blank, trimmed
- `storage_path`: If provided, must be within `~/.localclip/projects/` (security check)

---

##### `GET /api/v1/projects` — List Projects

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max results (1-100) |
| `offset` | int | 0 | Pagination offset |
| `sort` | string | `-last_opened_at` | Sort field: `name`, `created_at`, `updated_at`, `last_opened_at`. Prefix `-` for descending |

**Response Schema (200):**
```json
{
  "projects": [
    {
      "id": "uuid",
      "name": "Project Name",
      "description": "...",
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "last_opened_at": "ISO8601",
      "video_count": 3,
      "thumbnail_url": null,
      "duration_seconds": 3600
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

**Status Codes:** `200 OK`

---

##### `GET /api/v1/projects/{project_id}` — Get Project

**Response Schema (200):** Full project object as above plus:
```json
{
  "videos": [ /* ProjectVideo summaries */ ],
  "timeline": { /* TimelineState */ }
}
```

**Status Codes:** `200 OK` | `404 Not Found`

---

##### `PATCH /api/v1/projects/{project_id}` — Update Project

**Request Schema:**
```json
{
  "name": {"type": "string", "optional": true},
  "description": {"type": "string", "optional": true, "nullable": true}
}
```

**Status Codes:** `200 OK` | `400 Bad Request` | `404 Not Found`

---

##### `DELETE /api/v1/projects/{project_id}` — Delete Project

**Response (204):** No content.

**Status Codes:** `204 No Content` | `404 Not Found`

**Side Effects:** Deletes project directory, all associated files, and database records.

---

#### 6.2.2 Video Import Endpoints

##### `POST /api/v1/projects/{project_id}/videos` — Import Video

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | conditional | Local video file. Required unless `source_type=url`. |
| `source_type` | string | no | `local` (default) or `url` |
| `url` | string | conditional | YouTube URL. Required if `source_type=url`. |

**Validation Rules:**
- File extension must be one of: `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`
- File size must not exceed `max_import_size` (configurable, default 50 GB)
- File must pass FFprobe validation (must be a valid video with at least one video stream)
- If `source_type=url`, URL must be a valid YouTube URL (yt-dlp validation)

**Response Schema (201):**
```json
{
  "id": "uuid",
  "video_id": "uuid",
  "filename": "video.mp4",
  "hash": "sha256hex...",
  "status": "importing",
  "progress": 0.0,
  "metadata": {
    "duration_ms": 600000,
    "width": 1920,
    "height": 1080,
    "fps": 29.97,
    "video_codec": "h264",
    "audio_codec": "aac",
    "file_size_bytes": 524288000
  }
}
```

**Status Codes:** `201 Accepted` | `400 Bad Request` | `413 Payload Too Large` | `415 Unsupported Media Type` | `422 Unprocessable Entity` | `500 Internal Server Error`

**Error Codes:**
| Code | Condition |
|------|-----------|
| `ERR-IMPORT-001` | Unsupported file format |
| `ERR-IMPORT-002` | File size exceeds limit |
| `ERR-IMPORT-003` | Corrupted or unreadable file |
| `ERR-IMPORT-004` | YouTube download failed |
| `ERR-IMPORT-005` | Duplicate file (same hash) |
| `ERR-IMPORT-006` | Disk space insufficient |

---

##### `GET /api/v1/projects/{project_id}/videos` — List Project Videos

**Response (200):**
```json
{
  "videos": [
    {
      "id": "uuid",
      "video_id": "uuid",
      "filename": "video.mp4",
      "hash": "sha256hex...",
      "status": "ready",
      "metadata": { "...": "..." },
      "analysis_status": "completed",
      "imported_at": "ISO8601"
    }
  ]
}
```

---

##### `DELETE /api/v1/projects/{project_id}/videos/{video_id}` — Remove Video

**Response (204):** No content.

**Side Effects:** Removes video from project. Source file retained in VideoMaster (shared across projects). Analysis and clip data deleted.

---

#### 6.2.3 Analysis Endpoints

##### `POST /api/v1/projects/{project_id}/videos/{video_id}/analyze` — Start Analysis

**Request Schema:**
```json
{
  "pipeline_stages": {
    "transcribe": true,
    "diarize": true,
    "detect_scenes": true,
    "detect_silence": true,
    "analyze_semantic": true,
    "score_clips": true
  },
  "stt_model": {"type": "string", "default": "large-v3", "optional": true},
  "llm_model": {"type": "string", "optional": true}
}
```

**Response Schema (202):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_duration_seconds": 300,
  "pipeline_stages": ["preprocessing", "transcribing", "diarizing", "scene_detecting", "analyzing", "scoring"]
}
```

**Status Codes:** `202 Accepted` | `400 Bad Request` | `404 Not Found` | `409 Conflict` (already analyzing)

---

##### `GET /api/v1/projects/{project_id}/videos/{video_id}/analysis` — Get Analysis Results

**Response (200):**
```json
{
  "status": "completed",
  "transcript": {
    "segments": [
      {
        "start_ms": 0,
        "end_ms": 3200,
        "text": "Welcome to this video on...",
        "speaker": "Speaker A",
        "confidence": 0.98,
        "words": [
          {"word": "Welcome", "start_ms": 0, "end_ms": 400, "confidence": 0.99}
        ]
      }
    ],
    "language": "en",
    "language_confidence": 0.99
  },
  "speakers": [
    {"label": "Speaker A", "segments": [{"start_ms": 0, "end_ms": 120000}], "face_thumbnails": ["url"]}
  ],
  "scenes": [
    {"start_ms": 0, "end_ms": 30000, "type": "content", "description": "Intro", "keyframe_url": "/thumbnails/..."}
  ],
  "topics": [
    {"name": "Introduction", "start_ms": 0, "end_ms": 30000, "keywords": ["welcome", "overview"]}
  ],
  "keywords": ["AI", "video editing", "automation", "content creation"],
  "hooks": [
    {"time_ms": 2500, "score": 85, "text": "this tool will save you 10 hours per week", "type": "benefit"}
  ],
  "quality_scores": {
    "overall": 78,
    "dimensions": {
      "hook_strength": 82,
      "content_density": 75,
      "audio_clarity": 90,
      "visual_variety": 65,
      "structural_completeness": 80,
      "engagement_potential": 72
    }
  },
  "duration_ms": 600000
}
```

**Status Codes:** `200 OK` | `202 Accepted` (still processing) | `404 Not Found`

---

##### `DELETE /api/v1/projects/{project_id}/videos/{video_id}/analysis` — Clear Analysis

**Response (204):** No content. Analysis data deleted.

---

#### 6.2.4 Clip Endpoints

##### `POST /api/v1/projects/{project_id}/clips/generate` — Generate Clip Candidates

**Request Schema:**
```json
{
  "video_id": "uuid",
  "count": {"type": "integer", "default": 10, "min": 3, "max": 50},
  "min_duration_seconds": {"type": "integer", "default": 15},
  "max_duration_seconds": {"type": "integer", "default": 90},
  "score_threshold": {"type": "integer", "default": 50, "min": 0, "max": 100}
}
```

**Response (202):** Job ID for clip generation.

##### `GET /api/v1/projects/{project_id}/clips` — List Clip Candidates

**Query Parameters:** `video_id`, `status` (candidate/accepted/rejected), `sort` (-quality_score)

**Response (200):**
```json
{
  "clips": [
    {
      "id": "uuid",
      "video_id": "uuid",
      "start_ms": 45000,
      "end_ms": 75000,
      "duration_seconds": 30,
      "quality_score": 88,
      "virality_score": 72,
      "hook_score": 91,
      "title": "The AI Tool That Saves 10 Hours",
      "description": "Discover how this AI tool...",
      "hashtags": ["#AI", "#productivity", "#editing"],
      "status": "candidate",
      "rank": 1,
      "thumbnail_url": "/thumbnails/..."
    }
  ]
}
```

##### `PATCH /api/v1/projects/{project_id}/clips/{clip_id}` — Update Clip

**Request Schema:**
```json
{
  "status": {"type": "string", "enum": ["accepted", "rejected", "modified"]},
  "title": {"type": "string", "optional": true},
  "description": {"type": "string", "optional": true},
  "hashtags": {"type": "array", "optional": true},
  "start_ms": {"type": "integer", "optional": true},
  "end_ms": {"type": "integer", "optional": true}
}
```

##### `DELETE /api/v1/projects/{project_id}/clips/{clip_id}` — Delete Clip

---

#### 6.2.5 Timeline Endpoints

##### `GET /api/v1/projects/{project_id}/timeline` — Get Timeline State

**Response (200):**
```json
{
  "tracks": [
    {
      "id": "track-1",
      "type": "video",
      "name": "Video 1",
      "clips": [
        {
          "clip_id": "uuid",
          "source_video_id": "uuid",
          "start_ms": 0,
          "end_ms": 30000,
          "trim_start_ms": 0,
          "trim_end_ms": 0,
          "speed": 1.0,
          "effects": {"zoom": [{"time_ms": 5000, "scale": 1.2}]}
        }
      ]
    },
    {
      "id": "track-2",
      "type": "audio",
      "name": "Audio 1",
      "clips": []
    }
  ],
  "markers": [
    {"time_ms": 15000, "label": "Important moment", "color": "red"}
  ],
  "zoom_level": 1.0,
  "playhead_position_ms": 30000,
  "version": 5
}
```

##### `PUT /api/v1/projects/{project_id}/timeline` — Save Timeline State

**Request Schema:** Full timeline state as above.

**Response (200):** Updated timeline with new version number.

---

#### 6.2.6 Export Endpoints

##### `POST /api/v1/projects/{project_id}/exports` — Create Export Job

**Request Schema:**
```json
{
  "clip_id": "uuid",
  "format": {"type": "string", "enum": ["mp4", "mov", "webm", "srt", "vtt", "ass", "edl", "xml", "json"]},
  "preset": {"type": "string", "enum": ["high", "standard", "web", "proxy"], "default": "standard"},
  "resolution": {"type": "string", "pattern": "^\\d+x\\d+$", "optional": true},
  "include_captions": {"type": "boolean", "default": true},
  "caption_track_language": {"type": "string", "default": "en", "optional": true},
  "output_path": {"type": "string", "optional": true, "description": "Custom output directory"}
}
```

**Response (201):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_size_mb": 150,
  "estimated_duration_seconds": 45
}
```

##### `GET /api/v1/projects/{project_id}/exports` — List Export Jobs

##### `GET /api/v1/projects/{project_id}/exports/{job_id}` — Get Export Status

**Response (200):**
```json
{
  "job_id": "uuid",
  "status": "rendering",
  "progress": 0.65,
  "output_path": null,
  "error_message": null,
  "started_at": "ISO8601",
  "estimated_completion": "ISO8601"
}
```

##### `POST /api/v1/projects/{project_id}/exports/{job_id}/cancel` — Cancel Export

---

#### 6.2.7 AI Provider Endpoints

##### `GET /api/v1/providers` — List Providers

**Response (200):**
```json
{
  "providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "enabled": false,
      "supported_tasks": ["llm", "stt", "vision", "embedding"],
      "configured": true,
      "models_available": ["gpt-4o", "gpt-4o-mini", "whisper-1"]
    },
    {
      "id": "local",
      "name": "Local AI",
      "enabled": true,
      "supported_tasks": ["stt", "vision", "embedding"],
      "configured": true,
      "models_available": ["whisper-large-v3", "yolov8n-face", "all-MiniLM-L6-v2"]
    }
  ]
}
```

##### `PUT /api/v1/providers/{provider_id}` — Update Provider Config

**Request Schema:**
```json
{
  "enabled": {"type": "boolean", "optional": true},
  "api_key": {"type": "string", "optional": true, "writeOnly": true},
  "base_url": {"type": "string", "format": "uri", "optional": true},
  "models": {"type": "object", "optional": true},
  "defaults": {"type": "object", "optional": true}
}
```

`REQ-SRS-API-001`: API keys SHALL be encrypted before storage. The response SHALL NOT include the API key value. [P0]

##### `POST /api/v1/providers/{provider_id}/test` — Test Provider Connection

**Response (200):**
```json
{
  "success": true,
  "latency_ms": 350,
  "models_available": ["gpt-4o", "gpt-4o-mini"]
}
```

##### `GET /api/v1/providers/{provider_id}/models` — List Models for Provider

---

#### 6.2.8 Settings Endpoints

##### `GET /api/v1/settings` — Get All Settings

**Response (200):** Application settings object grouped by category.

##### `PATCH /api/v1/settings` — Update Settings

**Request Schema:** Partial settings object (merge semantics).

##### `GET /api/v1/settings/{category}` — Get Settings Category

Categories: `general`, `appearance`, `storage`, `gpu`, `ai_models`, `export`, `keyboard`, `cache`, `advanced`

---

#### 6.2.9 System Endpoints

##### `GET /api/v1/system/health` — Health Check

**Response (200):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "gpu": {
    "backend": "cuda",
    "device": "NVIDIA GeForce RTX 3060",
    "vram_total_mb": 12288,
    "vram_available_mb": 8192
  },
  "storage": {
    "app_directory": "/home/user/.localclip",
    "total_gb": 500,
    "used_gb": 120,
    "free_gb": 380
  },
  "queue_depth": 2,
  "active_jobs": 1
}
```

##### `GET /api/v1/system/gpu` — GPU Info

##### `GET /api/v1/system/storage` — Storage Usage

---

## 7. WebSocket Specification

### 7.1 Connection

`REQ-SRS-WS-001`: WebSocket endpoint at `ws://localhost:8765/api/v1/ws`. [P0]

`REQ-SRS-WS-002`: Connection SHALL be established without authentication. [P0]

### 7.2 Event Types

#### Server → Client Events

| Event | Payload | Trigger |
|-------|---------|---------|
| `job.progress` | `{job_id, job_type, stage, progress (0.0-1.0), message}` | Every progress update |
| `job.completed` | `{job_id, job_type, result_summary}` | Job finishes successfully |
| `job.failed` | `{job_id, job_type, error_code, error_message}` | Job fails |
| `pipeline.stage` | `{video_id, stage, status, progress}` | Pipeline stage transitions |
| `export.progress` | `{job_id, progress, fps, eta_seconds}` | Export frame-by-frame progress |
| `model.download` | `{model_id, progress, speed_mbps, eta}` | Model download progress |
| `system.warning` | `{code, message, severity}` | Storage warnings, GPU warnings |
| `system.error` | `{code, message}` | Unrecoverable system errors |

#### Client → Server Events

| Event | Payload | Purpose |
|-------|---------|---------|
| `subscribe` | `{channels: ["projects.{id}", "system"]}` | Subscribe to specific event channels |
| `unsubscribe` | `{channels: ["projects.{id}"]}` | Unsubscribe from channels |
| `ping` | `{}` | Keepalive |

### 7.3 Event Channel Pattern

`REQ-SRS-WS-003`: Clients SHALL subscribe to specific channels using a dot-notation pattern: [P0]

- `projects.{project_id}` — All events for a project
- `system` — System-level events
- `jobs.{job_id}` — Specific job progress

### 7.4 Connection Lifecycle

```
Client                     Server
  │                          │
  │── WebSocket Connect ────▶│
  │                          │── Accept connection
  │◀─── system.connected ────│
  │                          │
  │── subscribe: projects.x ─▶│
  │                          │── Register subscription
  │◀─── subscribed ──────────│
  │                          │
  │                          │── job.progress (push)
  │◀─── job.progress ────────│
  │                          │
  │── ping ─────────────────▶│
  │◀─── pong ────────────────│
  │                          │
  │── unsubscribe: projects.x│
  │── WebSocket Close ──────▶│
```

### 7.5 Keepalive

`REQ-SRS-WS-004`: Client SHALL send `ping` every 30 seconds. Server SHALL respond with `pong`. [P1]

`REQ-SRS-WS-005`: Server SHALL close connection if no message received for 120 seconds. [P1]

---

## 8. AI Pipeline Specification

### 8.1 Pipeline Architecture

The AI pipeline is composed of discrete stages connected in a directed acyclic graph (DAG). Each stage is an independently configurable and replaceable unit.

```
                    ┌─────────────────────┐
                    │   Preprocessing      │
                    │ (FFmpeg, validation) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  Audio       │ │  Video       │ │  Metadata    │
     │  Extraction  │ │  Frame Extr  │ │  Extraction  │
     └──────┬───────┘ └──────┬───────┘ └──────────────┘
            │                │
            ▼                ▼
     ┌──────────────┐ ┌──────────────┐
     │  STT         │ │  Scene Det   │
     │  (WhisperX)  │ │  (PyScene)   │
     └──────┬───────┘ └──────┬───────┘
            │                │
            ▼                ▼
     ┌──────────────┐ ┌──────────────┐
     │  Diarization │ │  Face Det    │
     │  (PyAnnote)  │ │  (YOLOv8)   │
     └──────┬───────┘ └──────┬───────┘
            │                │
            └──────┬─────────┘
                   ▼
            ┌──────────────┐
            │  Semantic    │
            │  Analysis    │
            │  (LLM)       │
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │  Clip        │
            │  Scoring     │
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │  Content Gen │
            │  (LLM)       │
            └──────────────┘
```

### 8.2 Stage Specifications

#### Stage 1: Preprocessing

| Property | Specification |
|----------|---------------|
| **Input** | Source video file path |
| **Outputs** | Audio WAV (16kHz mono), frame directory (1fps JPEG), proxy video (720p H.264), metadata |
| **Tools** | FFmpeg, FFprobe |
| **Models** | None |
| **Performance Target** | 5x real-time (e.g., 10-min video → 2 min preprocessing) |
| **Hardware** | CPU (multi-threaded) |
| **Cache Policy** | Cache by source hash + parameters. Cache key: `{hash}_preprocessed` |
| **Failure Recovery** | Transient failures: retry up to 3 times. Corrupted source: mark as invalid, skip pipeline. |

**Sub-operations:**
1. Validate file integrity (attempt full decode of first 10 seconds)
2. Extract metadata (FFprobe)
3. Extract audio: `ffmpeg -i input -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav`
4. Extract frames: `ffmpeg -i input -vf fps=1 output_dir/frame_%05d.jpg`
5. Generate proxy: `ffmpeg -i input -vf scale=1280:720 -c:v libx264 -crf 23 -preset fast -an output_proxy.mp4`
6. Compute SHA-256 hash of source file

---

#### Stage 2: Speech-to-Text (STT)

| Property | Specification |
|----------|---------------|
| **Input** | Audio WAV (16kHz mono) |
| **Outputs** | Segmented transcript with word-level timestamps, language, confidence scores |
| **Default Model** | WhisperX large-v3 (~3 GB VRAM) |
| **Plugin Interface** | `STTProvider` |
| **Performance Target** | 6x real-time on RTX 3060 (10-min audio → 100 sec) |
| **Hardware** | GPU (CUDA/MPS) or CPU |
| **Cache Policy** | Cache by audio SHA-256. Cache key: `{audio_hash}_stt_{model_name}` |
| **Failure Recovery** | OOM: fall back to medium model → small model → CPU. Timeout (>30 min): retry with smaller model. |

**Output Schema:**
```json
{
  "segments": [
    {
      "start_ms": 0,
      "end_ms": 3200,
      "text": "Welcome to this video",
      "speaker": "SPEAKER_00",
      "confidence": 0.98,
      "words": [
        {"word": "Welcome", "start_ms": 0, "end_ms": 400, "confidence": 0.99, "speaker": "SPEAKER_00"}
      ]
    }
  ],
  "language": "en",
  "language_confidence": 0.99
}
```

---

#### Stage 3: Speaker Diarization

| Property | Specification |
|----------|---------------|
| **Input** | Audio WAV (16kHz mono), transcript segments |
| **Outputs** | Speaker-labeled segments with speaker count |
| **Default Tool** | PyAnnote Audio 3.1 |
| **Alternatives** | WhisperX built-in diarization, or skip if using STT with diarization |
| **Performance Target** | 4x real-time on RTX 3060 |
| **Hardware** | GPU preferred |
| **Cache Policy** | Cache by audio hash. Cache key: `{audio_hash}_diarization` |

**Output Schema:**
```json
{
  "speakers": [
    {"label": "SPEAKER_00", "num_segments": 42, "total_seconds": 320.5},
    {"label": "SPEAKER_01", "num_segments": 28, "total_seconds": 180.2}
  ],
  "segments": [
    {"start_ms": 0, "end_ms": 3200, "speaker": "SPEAKER_00", "confidence": 0.95}
  ]
}
```

---

#### Stage 4: Scene Detection

| Property | Specification |
|----------|---------------|
| **Input** | Frame directory (JPEG, 1fps), video file |
| **Outputs** | Scene boundaries with type classification |
| **Default Tool** | PySceneDetect (content detection + adaptive threshold) |
| **Plugins** | SceneDetectProvider |
| **Performance Target** | 10x real-time |
| **Hardware** | CPU |
| **Cache Policy** | Cache by frame directory hash |

**Algorithm:**
1. Content detection: `detect-content(threshold=30)` — detects cuts by frame content difference
2. Adaptive threshold: `detect-adaptive(threshold=3.0, min-scene-len=1.0s)` — detects gradual transitions
3. Merge adjacent scenes shorter than 0.5s into surrounding scenes
4. Classify scene type by visual properties (static, motion, black frame, interview)

**Output Schema:**
```json
{
  "scenes": [
    {"start_ms": 0, "end_ms": 15000, "type": "intro", "keyframe_path": "frame_00001.jpg"},
    {"start_ms": 15000, "end_ms": 45000, "type": "interview", "keyframe_path": "frame_00015.jpg"}
  ]
}
```

---

#### Stage 5: Visual Analysis

| Property | Specification |
|----------|---------------|
| **Input** | Frame directory, scene boundaries, speaker segments |
| **Outputs** | Face bounding boxes per frame, tracked speakers, object regions |
| **Default Model** | YOLOv8n-face (6 MB) |
| **Plugins** | VisionProvider |
| **Performance Target** | 15fps face detection on RTX 3060 |
| **Hardware** | GPU preferred |
| **Cache Policy** | Cache by frame range + model hash |

**Output Schema:**
```json
{
  "face_tracks": [
    {
      "speaker": "SPEAKER_00",
      "track_id": 0,
      "keyframes": [
        {"frame": 150, "bbox": [0.2, 0.1, 0.4, 0.8], "confidence": 0.95}
      ],
      "segments": [{"start_ms": 0, "end_ms": 120000}]
    }
  ],
  "frame_analyses": [
    {"frame_index": 150, "faces": [{"bbox": [0.2, 0.1, 0.4, 0.8], "track_id": 0}]}
  ]
}
```

---

#### Stage 6: Semantic Analysis (LLM)

| Property | Specification |
|----------|---------------|
| **Input** | Transcript with speakers, scene list, keywords |
| **Outputs** | Topics, hooks, chapter markers, keywords, emotion labels |
| **Default Model** | Qwen 2.5 7B (GGUF, via llama.cpp) |
| **Plugins** | LLMProvider |
| **Performance Target** | < 1 min per hour of transcript |
| **Hardware** | GPU (4GB+ VRAM) or CPU (slower) |
| **Cache Policy** | Cache by transcript hash + LLM params + prompt version |

**LLM Prompt Structure:**
```
SYSTEM: You are a video content analyst. Analyze the following transcript and:
1. Identify 3-7 major topics discussed
2. Identify the 3-5 most "hook-worthy" moments (engaging, surprising, valuable)
3. Generate chapter markers with descriptive titles
4. Extract 10-20 key phrases/keywords
5. Classify the emotional tone per segment (positive/negative/neutral/excitement)
6. Suggest a hook improvement for the first 5 seconds

TRANSCRIPT:
[timestamped transcript with speaker labels]

OUTPUT FORMAT (JSON):
{
  "topics": [{"name": "...", "start_ms": ..., "end_ms": ..., "keywords": [...]}],
  "hooks": [{"time_ms": ..., "text": "..." , "type": "benefit|surprise|question|story", "score": 0-100}],
  "chapters": [{"start_ms": ..., "title": "..."}],
  "keywords": ["...", "..."],
  "emotions": [{"start_ms": ..., "end_ms": ..., "emotion": "positive|negative|neutral|excitement"}],
  "hook_suggestion": "Start with: '...' instead of '...'"
}
```

---

#### Stage 7: Clip Generation & Scoring

| Property | Specification |
|----------|---------------|
| **Input** | All previous analysis outputs |
| **Outputs** | Ranked clip candidates with scores |
| **Models** | None (deterministic algorithm) |
| **Performance Target** | < 30 seconds per hour of video |
| **Hardware** | CPU |
| **Cache Policy** | By all input hashes combined |

**Scoring Algorithm:**
```
hook_strength (25%):
  - Hook score from LLM (0-100)
  - First 3 seconds engagement signal
  - Adjust: -10 if first 3s has silence, +5 if question/surprise detected

content_density (20%):
  - Words per second (target: 2.5-4.0)
  - Silence ratio (penalize > 30% or < 5%)
  - Topic transitions per minute

audio_clarity (15%):
  - Average STT confidence score
  - Noise floor estimate (from audio analysis)
  - Penalize: background music without speech

visual_variety (15%):
  - Scene changes per minute (target: 2-8)
  - Face presence ratio
  - Camera motion detected

structural_completeness (15%):
  - Has clear opening hook (0-3s)
  - Has clear main content
  - Has clear conclusion/CTA

engagement_potential (10%):
  - Emotional variety score
  - Question count
  - Call-to-action presence
  - Keyword relevance (trending topics)

final_score = weighted_average(all_dimensions)
```

---

#### Stage 8: Content Generation (LLM)

| Property | Specification |
|----------|---------------|
| **Input** | Clip transcript, scene context |
| **Outputs** | Title, description, hashtags |
| **Model** | Same LLM from stage 6 |
| **Performance Target** | < 10 seconds per clip |
| **Cache Policy** | By clip content hash |

---

### 8.3 Pipeline Execution Model

`REQ-SRS-PIPE-001`: Pipeline SHALL execute asynchronously via Celery task queue. [P0]

`REQ-SRS-PIPE-002`: Pipeline SHALL support cancellation — setting status to `cancelled` SHALL stop execution via a stop event pattern. [P1]

`REQ-SRS-PIPE-003`: Pipeline progress SHALL be reported via WebSocket after each stage completes. [P0]

`REQ-SRS-PIPE-004`: Pipeline SHALL persist intermediate results after each stage to enable resumption. [P2]

`REQ-SRS-PIPE-005`: Each stage SHALL respect a configurable timeout (default: 30 min per stage). On timeout, stage SHALL be marked as failed. [P1]

---

## 9. Plugin Architecture

### 9.1 Plugin Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    PLUGIN LIFECYCLE                          │
│                                                             │
│  DISCOVERED ──▶ LOADED ──▶ INITIALIZED ──▶ ACTIVE ──▶ SHUTDOWN  │
│     │              │             │              │           │
│     └──(invalid)──▶ ERROR ◀──────┘              │           │
│                                                  │           │
│                                            HEALTH_CHECK      │
│                                                  │           │
│                                         ┌────────┴────────┐  │
│                                         │  healthy / not  │  │
│                                         └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Plugin Manifest

```json
{
  "name": "whisperx-stt",
  "version": "1.0.0",
  "min_app_version": "1.0.0",
  "type": "stt",
  "author": "Local Clip Studio",
  "description": "WhisperX speech-to-text provider",
  "entry_point": "plugin.py:WhisperXSTTPlugin",
  "dependencies": {
    "python": ">=3.11",
    "pip": ["whisper-x", "torch>=2.1"],
    "models": ["whisper-large-v3"]
  },
  "permissions": ["gpu", "network:localhost"],
  "capabilities": ["diarization", "word_timestamps", "language_detection"],
  "models": [
    {"id": "tiny", "size_mb": 150, "vram_mb": 1000, "performance": "10x realtime"},
    {"id": "large-v3", "size_mb": 3000, "vram_mb": 3500, "performance": "6x realtime"}
  ]
}
```

### 9.3 Plugin Interfaces

#### STT Provider Interface

```python
# srs/plugins/interfaces/stt.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WordTiming:
    word: str
    start_ms: int
    end_ms: int
    confidence: float
    speaker: str | None = None

@dataclass
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float = 1.0
    words: list[WordTiming] = None

@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment]
    language: str
    language_confidence: float
    duration_ms: int

class STTProvider(ABC):
    @abstractmethod
    async def load(self, model_id: str = "large-v3") -> None:
        """Load model. Called once during initialization."""
        ...

    @abstractmethod
    async def transcribe(self, audio_path: str, language: str | None = None) -> TranscriptResult:
        """Transcribe audio file. Returns word-level transcript."""
        ...

    @abstractmethod
    async def get_available_models(self) -> list[dict]:
        """Return list of available models with metadata."""
        ...

    @abstractmethod
    async def unload(self) -> None:
        """Unload model and free resources."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Return health status: {'status': 'ok', 'latency_ms': 100}."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> set[str]:
        """Return set of capabilities: {'diarization', 'word_timestamps', 'language_detection'}."""
        ...
```

#### LLM Provider Interface

```python
# srs/plugins/interfaces/llm.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None  # {"prompt_tokens": N, "completion_tokens": N}
    latency_ms: int

class LLMProvider(ABC):
    @abstractmethod
    async def load(self, model_id: str | None = None) -> None:
        """Load model. If None, use default."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse | list[str]:
        """Generate text from messages. If stream=True, yield chunks."""
        ...

    @abstractmethod
    async def get_available_models(self) -> list[dict]:
        """Return available models."""
        ...

    @abstractmethod
    async def unload(self) -> None:
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        ...
```

#### Vision Provider Interface

```python
# srs/plugins/interfaces/vision.py

@dataclass
class BoundingBox:
    x: float  # normalized 0-1
    y: float
    width: float
    height: float

@dataclass
class Detection:
    bbox: BoundingBox
    label: str
    confidence: float
    track_id: int | None = None

@dataclass
class VisionResult:
    detections: list[Detection]
    frame_index: int
    processing_time_ms: float

class VisionProvider(ABC):
    @abstractmethod
    async def load(self, model_id: str = "yolov8n-face") -> None: ...

    @abstractmethod
    async def detect(self, image_path: str) -> VisionResult: ...

    @abstractmethod
    async def detect_batch(self, image_paths: list[str]) -> list[VisionResult]: ...
```

### 9.4 Plugin Registry

`REQ-SRS-PLUG-001`: Plugin registry SHALL discover plugins from the `plugins/` directory on startup. [P0]

`REQ-SRS-PLUG-002`: Plugin registry SHALL validate manifest against schema before loading. [P0]

`REQ-SRS-PLUG-003`: Plugin registry SHALL maintain a map of `type → [PluginInstance]` for runtime lookup. [P0]

`REQ-SRS-PLUG-004`: Plugin registry SHALL support `get_best_provider(task_type)` which returns the highest-priority enabled provider. [P0]

`REQ-SRS-PLUG-005`: Plugin registry SHALL support fallback chains: if primary plugin fails, try next-enabled. [P1]

---

## 10. Service Contracts

### 10.1 ProjectService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | CRUD operations for projects, project lifecycle management, recent project tracking |
| **Dependencies** | `ProjectRepository`, `FileSystemService` |
| **Failure Modes** | Database errors → log + return 500. File system errors → log + return actionable error. |

**Public Interface:**
```python
class ProjectService:
    async def create(self, name: str, description: str | None, storage_path: str | None) -> Project: ...
    async def get(self, project_id: str) -> Project | None: ...
    async def list(self, limit: int = 20, offset: int = 0, sort: str = "-last_opened_at") -> list[Project]: ...
    async def update(self, project_id: str, updates: dict) -> Project: ...
    async def delete(self, project_id: str) -> None: ...
    async def get_recent(self, count: int = 10) -> list[Project]: ...
    async def duplicate(self, project_id: str, new_name: str) -> Project: ...
    async def archive(self, project_id: str) -> str:  # returns archive path
    async def restore(self, archive_path: str) -> Project: ...
```

### 10.2 ImportService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | File validation, hash deduplication, copy to project storage, metadata extraction, proxy generation |
| **Dependencies** | `VideoMasterRepository`, `ProjectVideoRepository`, `FileSystemService`, `FFmpegService`, `HALRegistry` |
| **Failure Modes** | Corrupted file → ERR-IMPORT-003. Disk full → ERR-IMPORT-006. Duplicate → ERR-IMPORT-005. |

**Public Interface:**
```python
class ImportService:
    async def import_file(self, project_id: str, file_path: str) -> ProjectVideo: ...
    async def import_url(self, project_id: str, url: str) -> ProjectVideo: ...
    async def get_import_status(self, project_video_id: str) -> dict: ...
    async def cancel_import(self, project_video_id: str) -> None: ...
```

### 10.3 PipelineService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | Orchestrating AI pipeline execution, stage management, progress reporting, caching |
| **Dependencies** | All plugin providers, `AnalysisRepository`, `JobQueue`, `FileSystemService`, `HALRegistry` |
| **Failure Modes** | STT failure → retry with different model. LLM failure → fallback provider. OOM → fallback to CPU. |

**Public Interface:**
```python
class PipelineService:
    async def start_analysis(self, project_id: str, video_id: str, config: dict) -> str:  # job_id
    async def get_analysis(self, project_id: str, video_id: str) -> Analysis | None: ...
    async def cancel_analysis(self, project_id: str, video_id: str) -> None: ...
    async def generate_clips(self, project_id: str, video_id: str, params: dict) -> list[ClipCandidate]: ...
    async def get_pipeline_status(self, project_id: str, video_id: str) -> PipelineStatus: ...
```

### 10.4 ExportService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | FFmpeg command construction, GPU encoder selection, progress monitoring, format conversion |
| **Dependencies** | `FFmpegService`, `HALRegistry`, `ExportJobRepository`, `CaptionTrackRepository` |
| **Failure Modes** | GPU encoder unavailable → fallback to software. Export timeout → retry with lower quality. |

**Public Interface:**
```python
class ExportService:
    async def create_job(self, project_id: str, clip_id: str, config: ExportConfig) -> ExportJob: ...
    async def get_job(self, job_id: str) -> ExportJob: ...
    async def list_jobs(self, project_id: str, status: str | None = None) -> list[ExportJob]: ...
    async def cancel_job(self, job_id: str) -> None: ...
    async def get_presets(self) -> list[ExportPreset]: ...
```

### 10.5 ProviderService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | Provider configuration, model discovery, connection testing, fallback management |
| **Dependencies** | `SettingsRepository`, Plugin Registry |
| **Failure Modes** | Invalid API key → test fails. Provider unreachable → marked offline. |

**Public Interface:**
```python
class ProviderService:
    async def list_providers(self) -> list[ProviderInfo]: ...
    async def update_provider(self, provider_id: str, config: dict) -> ProviderInfo: ...
    async def test_connection(self, provider_id: str) -> ConnectionTestResult: ...
    async def get_models(self, provider_id: str) -> list[ModelInfo]: ...
    async def get_active_provider(self, task_type: str) -> ProviderInstance: ...
```

### 10.6 SettingsService

| Property | Specification |
|----------|---------------|
| **Responsibilities** | Read/write settings, validation, change event notification |
| **Dependencies** | `SettingsRepository` |
| **Failure Modes** | Corrupt settings file → create new with defaults. Validation error → return with field-specific errors. |

**Public Interface:**
```python
class SettingsService:
    async def get_all(self) -> dict: ...
    async def get_category(self, category: str) -> dict: ...
    async def update(self, updates: dict) -> dict: ...  # merge semantics
    async def reset_category(self, category: str) -> dict: ...
    async def export(self) -> str: ...  # export config as JSON
    async def import_config(self, config_json: str) -> dict: ...
```

---

## 11. State Machines

### 11.1 Project State Machine

```
[CREATED] ──▶ [ACTIVE] ──▶ [DELETED]
                 │
                 ├──▶ [ARCHIVED] ──▶ [ACTIVE] (restore)
                 │
                 └──▶ [DUPLICATING] ──▶ [ACTIVE] (new project)
```

| Transition | Trigger | Guard Condition |
|------------|---------|-----------------|
| CREATED → ACTIVE | Project directory created + DB record saved | Always valid |
| ACTIVE → DELETED | User deletes project | Confirm dialog shown |
| ACTIVE → ARCHIVED | User archives project | No active processing jobs |
| ARCHIVED → ACTIVE | User restores archive | Archive file exists |

### 11.2 Upload State Machine

```
[PENDING] ──▶ [VALIDATING] ──▶ [IMPORTING] ──▶ [READY]
                 │                  │
                 ▼                  ▼
              [FAILED]           [FAILED]
                 ▲
                 │
              [CANCELLED]
```

| Transition | Trigger | Guard Condition |
|------------|---------|-----------------|
| PENDING → VALIDATING | Upload request accepted | File exists |
| VALIDATING → IMPORTING | Validation passed | File passes FFprobe |
| VALIDATING → FAILED | Validation failed | See error catalog |
| IMPORTING → READY | File copied + metadata extracted | Success |
| IMPORTING → FAILED | Copy/process error | See error catalog |
| PENDING → CANCELLED | User cancels | Always valid |
| IMPORTING → CANCELLED | User cancels | Should confirm data loss |

### 11.3 AI Job State Machine

```
[QUEUED] ──▶ [PREPROCESSING] ──▶ [TRANSCRIBING] ──▶ [DIARIZING] ──▶ [SCENE_DETECTING] ──▶ [ANALYZING] ──▶ [SCORING] ──▶ [COMPLETED]
   │              │                    │                  │                   │                  │              │
   ▼              ▼                    ▼                  ▼                   ▼                  ▼              ▼
[CANCELLED]    [FAILED]              [FAILED]           [FAILED]            [FAILED]           [FAILED]       [FAILED]

Each stage can transition to FAILED independently:
  QUEUED ──▶ CANCELLED (user cancels before start)
  QUEUED ──▶ FAILED (internal error)
  Any active stage ──▶ FAILED (transient error → retry → permanent failure)
  Any active stage ──▶ CANCELLED (user cancels mid-processing)
```

| Invalid Transitions | Reason |
|---------------------|--------|
| COMPLETED → any | Terminal state |
| FAILED → any | Terminal state (user must retry from start) |
| COMPLETED → COMPLETED | Idempotent |
| Skip stages forward | All stages must execute in order |

### 11.4 Export State Machine

```
[PENDING] ──▶ [RENDERING] ──▶ [COMPLETED]
   │              │
   ▼              ▼
[CANCELLED]    [FAILED]
```

| Transition | Trigger |
|------------|---------|
| PENDING → RENDERING | Worker picks up job |
| RENDERING → COMPLETED | FFmpeg exits with code 0 |
| RENDERING → FAILED | FFmpeg error, timeout, or OOM |
| PENDING → CANCELLED | User cancels before start |
| RENDERING → CANCELLED | User cancels mid-export (partial file deleted) |

### 11.5 Model Download State Machine

```
[PENDING] ──▶ [DOWNLOADING] ──▶ [VERIFYING] ──▶ [READY]
   │               │                │
   ▼               ▼                ▼
[CANCELLED]    [FAILED]          [FAILED] ──▶ [DOWNLOADING] (retry)
```

### 11.6 Plugin Lifecycle State Machine

```
[DISCOVERED] ──▶ [LOADED] ──▶ [INITIALIZED] ──▶ [ACTIVE] ◀──▶ [HEALTH_CHECK] (periodic)
     │                │               │
     ▼                ▼               ▼
   [ERROR]          [ERROR]         [ERROR] ──▶ [SHUTDOWN]
                                                │
                                                ▼
                                             [DISABLED]
```

---

## 12. Error Catalog

### 12.1 Error Code Format

`ERR-{CATEGORY}-{NNN}`

### 12.2 Error Catalog

#### Import Errors (ERR-IMP)

| Code | Category | Severity | Message | Recovery | Log Level |
|------|----------|----------|---------|----------|-----------|
| ERR-IMP-001 | Validation | ERROR | "Unsupported file format. Supported formats: MP4, MOV, MKV, AVI, WebM" | User selects a supported file | WARNING |
| ERR-IMP-002 | Validation | ERROR | "File exceeds maximum import size of {limit_gb} GB. Current file: {size_gb} GB" | User reduces file size or increases limit | WARNING |
| ERR-IMP-003 | Validation | ERROR | "File appears to be corrupted or unreadable. FFprobe could not decode the file." | User verifies source file integrity | ERROR |
| ERR-IMP-004 | Download | ERROR | "YouTube download failed: {reason}" | User checks URL and internet connection | ERROR |
| ERR-IMP-005 | Duplicate | INFO | "This file has already been imported (SHA-256: {hash_prefix}...). Skipping." | Automatically skipped | INFO |
| ERR-IMP-006 | Storage | ERROR | "Insufficient disk space. Required: {required_gb} GB, Available: {available_gb} GB" | User frees disk space | ERROR |
| ERR-IMP-007 | Storage | WARNING | "Storage limit for this category ({category}) has been exceeded. ({used}/{limit})" | User adjusts storage limits | WARNING |

#### Pipeline Errors (ERR-PIPE)

| Code | Category | Severity | Message | Recovery | Log Level |
|------|----------|----------|---------|----------|-----------|
| ERR-PIPE-001 | STT | ERROR | "Speech-to-text failed: {reason}" | Retry with different model or provider | ERROR |
| ERR-PIPE-002 | STT | WARNING | "STT model not found. Download required ({size_gb} GB)." | Auto-download model | WARNING |
| ERR-PIPE-003 | GPU | ERROR | "GPU out of memory. Required: {required_mb} MB, Available: {available_mb} MB" | Fallback to smaller model or CPU | ERROR |
| ERR-PIPE-004 | GPU | INFO | "GPU not available. Falling back to CPU processing (slower)." | Automatic fallback | INFO |
| ERR-PIPE-005 | LLM | ERROR | "LLM provider returned an error: {status_code} {message}" | Fallback to next configured provider | ERROR |
| ERR-PIPE-006 | LLM | WARNING | "LLM response timeout after {timeout}s" | Retry with more retries | WARNING |
| ERR-PIPE-007 | Pipeline | ERROR | "Pipeline stage '{stage}' timed out after {timeout}s" | Retry stage | ERROR |
| ERR-PIPE-008 | Pipeline | INFO | "No audio track detected. Speech recognition will be skipped." | Continue with visual-only pipeline | INFO |
| ERR-PIPE-009 | Pipeline | WARNING | "Video contains no speech. Clip generation will use visual analysis only." | Adjust clip generation strategy | WARNING |

#### Export Errors (ERR-EXP)

| Code | Category | Severity | Message | Recovery | Log Level |
|------|----------|----------|---------|----------|-----------|
| ERR-EXP-001 | Encoding | ERROR | "Export failed: FFmpeg returned error code {code}. {stderr}" | Check log for details, retry | ERROR |
| ERR-EXP-002 | Encoding | WARNING | "GPU encoder unavailable ({encoder}). Falling back to software encoding." | Automatic fallback | WARNING |
| ERR-EXP-003 | Storage | ERROR | "Export failed: insufficient disk space at {path}" | User frees disk space | ERROR |
| ERR-EXP-004 | Format | ERROR | "Unsupported export format: {format}" | User selects supported format | WARNING |
| ERR-EXP-005 | Timeout | ERROR | "Export timed out after {timeout}s" | Try lower quality preset | ERROR |

#### System Errors (ERR-SYS)

| Code | Category | Severity | Message | Recovery | Log Level |
|------|----------|----------|---------|----------|-----------|
| ERR-SYS-001 | Startup | ERROR | "FFmpeg not found. Install FFmpeg 6.0+ and ensure it's in PATH." | User installs FFmpeg | ERROR |
| ERR-SYS-002 | Startup | ERROR | "Application directory could not be created at {path}: {error}" | User checks permissions | ERROR |
| ERR-SYS-003 | Database | ERROR | "Database error: {detail}" | Application restart, check logs | CRITICAL |
| ERR-SYS-004 | Security | ERROR | "Path traversal detected: {path}" | Request rejected | CRITICAL |
| ERR-SYS-005 | Config | WARNING | "Settings file corrupted. Restored defaults." | Automatic recovery | WARNING |
| ERR-SYS-006 | Memory | WARNING | "System memory low ({available_mb} MB available). Close other applications." | User closes applications | WARNING |

#### Plugin Errors (ERR-PLUG)

| Code | Category | Severity | Message | Recovery | Log Level |
|------|----------|----------|---------|----------|-----------|
| ERR-PLUG-001 | Load | ERROR | "Plugin '{name}' failed to load: {error}" | User checks plugin compatibility | ERROR |
| ERR-PLUG-002 | Manifest | WARNING | "Plugin '{name}' manifest is invalid: {error}" | Plugin developer fixes manifest | WARNING |
| ERR-PLUG-003 | Runtime | ERROR | "Plugin '{name}' crashed: {error}" | Plugin disabled, user reports issue | ERROR |
| ERR-PLUG-004 | Permission | ERROR | "Plugin '{name}' requested permission '{perm}' which was denied" | User reviews plugin permissions | WARNING |

### 12.3 Error Response Format

```json
{
  "error": {
    "code": "ERR-IMP-001",
    "message": "Unsupported file format. Supported formats: MP4, MOV, MKV, AVI, WebM",
    "details": {
      "provided_format": ".wmv",
      "supported_formats": [".mp4", ".mov", ".mkv", ".avi", ".webm"]
    },
    "request_id": "req-uuid-here",
    "timestamp": "2026-06-29T10:00:00Z"
  }
}
```

---

## 13. Testing Specification

### 13.1 Test Categories

#### Unit Tests

`REQ-SRS-TEST-001`: Every service method SHALL have at least one unit test. [P0]

`REQ-SRS-TEST-002`: Unit tests SHALL mock all external dependencies (database, filesystem, FFmpeg, HAL). [P0]

`REQ-SRS-TEST-003`: Unit tests SHALL cover: normal execution, error paths, boundary conditions. [P0]

`REQ-SRS-TEST-004`: Minimum unit test coverage: 85% for service layer, 90% for domain layer. [P1]

**Target files:**
- `tests/unit/services/test_project_service.py`
- `tests/unit/services/test_import_service.py`
- `tests/unit/services/test_pipeline_service.py`
- `tests/unit/services/test_export_service.py`
- `tests/unit/services/test_provider_service.py`
- `tests/unit/domain/test_project.py`
- `tests/unit/domain/test_video.py`
- `tests/unit/domain/test_clip.py`
- `tests/unit/hal/test_hal_registry.py`
- `tests/unit/hal/test_cpu_provider.py`
- `tests/unit/pipeline/test_quality_scorer.py`
- `tests/unit/pipeline/test_clip_generator.py`

#### Integration Tests

`REQ-SRS-TEST-005`: Integration tests SHALL use a real SQLite in-memory database. [P0]

`REQ-SRS-TEST-006`: Integration tests SHALL test API endpoints end-to-end with real request/response. [P0]

`REQ-SRS-TEST-007`: Integration tests SHALL cover: happy path, validation errors, database errors. [P1]

**Target files:**
- `tests/integration/test_project_api.py`
- `tests/integration/test_import_api.py`
- `tests/integration/test_analysis_api.py`
- `tests/integration/test_export_api.py`
- `tests/integration/test_provider_api.py`
- `tests/integration/test_websocket.py`
- `tests/integration/test_settings_api.py`

#### End-to-End Tests

`REQ-SRS-TEST-008`: E2E tests SHALL test complete user workflows against a running backend. [P1]

`REQ-SRS-TEST-009`: E2E tests SHALL use test video fixtures (< 30 seconds, all supported formats). [P1]

**Target workflows:**
1. Import video → analyze → view transcript → generate clips → accept clip → export MP4
2. Import YouTube URL → analyze → generate clips → export SRT
3. Create project → add multiple videos → batch process → export all
4. Configure provider → test connection → run pipeline with new provider

#### Performance Tests

`REQ-SRS-TEST-010`: Performance tests SHALL benchmark each pipeline stage against target metrics. [P1]

`REQ-SRS-TEST-011`: Performance tests SHALL run on reference hardware (RTX 3060, 32GB RAM, NVMe). [P1]

`REQ-SRS-TEST-012`: Performance regression SHALL be detected (any stage > 20% slower than baseline). [P2]

**Benchmark targets:**
- STT: 6x real-time on RTX 3060
- Scene detection: 10x real-time
- Face detection: 15fps
- Export: > 60fps with NVENC at 1080p

#### Failure Tests

`REQ-SRS-TEST-013`: Failure tests SHALL verify system behavior under: GPU OOM, disk full, corrupted files, missing FFmpeg, network timeout. [P1]

`REQ-SRS-TEST-014`: Each failure mode SHALL produce the correct error code from the error catalog. [P1]

### 13.2 Test Infrastructure

| Tool | Purpose |
|------|---------|
| **pytest** | Test runner |
| **pytest-asyncio** | Async test support |
| **pytest-cov** | Coverage reporting |
| **httpx** | Async HTTP test client |
| **pytest-benchmark** | Performance benchmarks |
| **factory-boy** | Test fixtures |
| **freezegun** | Time mocking |

### 13.3 CI Requirements

`REQ-SRS-TEST-015`: Unit + integration tests SHALL run in < 60 seconds. [P0]

`REQ-SRS-TEST-016`: All tests SHALL pass before release. No regression allowed. [P0]

---

## 14. Security Specification

### 14.1 File Security

`REQ-SRS-SEC-001`: All file path inputs MUST be validated against path traversal attacks. Path components containing `..` or starting with `/` (absolute paths outside allowed directories) MUST be rejected. [P0]

`REQ-SRS-SEC-002`: Imported files MUST be validated by FFprobe before acceptance. Malformed files MUST be rejected. [P0]

`REQ-SRS-SEC-003`: Source video files MUST be stored as read-only after import (OS-level permissions). [P1]

### 14.2 API Key Security

`REQ-SRS-SEC-004`: API keys MUST be encrypted at rest using AES-256-GCM. The encryption key MUST be derived from a machine-specific identifier. [P0]

`REQ-SRS-SEC-005`: API keys MUST NEVER be: logged, included in error messages, transmitted to any endpoint other than the configured provider, included in API responses. [P0]

`REQ-SRS-SEC-006`: The settings page MUST display API key fields as password-masked inputs. [P0]

### 14.3 Plugin Security

`REQ-SRS-SEC-007`: Plugins MUST declare required permissions in their manifest. The permission system SHALL restrict: filesystem access, network access, GPU access. [P1]

`REQ-SRS-SEC-008`: Plugins SHOULD be executed in a subprocess with restricted permissions. [P2]

### 14.4 Network Security

`REQ-SRS-SEC-009`: The application MUST NOT make any network requests except: model downloads (user-initiated), YouTube imports (user-initiated), configured AI providers (user-initiated). [P0]

`REQ-SRS-SEC-010`: The application MUST NOT contain any telemetry, analytics, crash reporting, or usage tracking that transmits data off-device. [P0]

---

## 15. Non-Functional Requirements

### 15.1 Performance

| ID | Metric | Target | Measurement |
|----|--------|--------|-------------|
| NFR-PERF-001 | Cold startup time | < 5 seconds | Time from process start to API readiness |
| NFR-PERF-002 | Timeline scrub latency | < 100ms | Input to proxy frame displayed |
| NFR-PERF-003 | Export throughput (1080p NVENC) | > 60fps | Output frames per second |
| NFR-PERF-004 | Pipeline (10min video, RTX 3060) | < 5 minutes | Total pipeline duration |
| NFR-PERF-005 | API response time (p95) | < 200ms | Excluding file uploads |
| NFR-PERF-006 | Concurrent pipeline jobs | 2 | Simultaneous pipeline executions |
| NFR-PERF-007 | GPU memory utilization | < 80% | Peak VRAM / Total VRAM |
| NFR-PERF-008 | Auto-save latency | < 500ms | Trigger to persistence |

### 15.2 Reliability

| ID | Metric | Target |
|----|--------|--------|
| NFR-REL-001 | Pipeline completion rate | > 95% of jobs |
| NFR-REL-002 | Crash recovery data loss | < 60 seconds of work |
| NFR-REL-003 | Error log coverage | 100% of errors logged |
| NFR-REL-004 | Uptime (excluding user system) | 99.9% |

### 15.3 Compatibility

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-COMP-001 | OS support | Linux (Ubuntu 22.04+, Fedora 38+), macOS 13+, Windows 10+ |
| NFR-COMP-002 | Browsers | Chrome 120+, Firefox 121+, Edge 120+, Safari 17+ |
| NFR-COMP-003 | Python | 3.11, 3.12 |
| NFR-COMP-004 | GPU drivers | CUDA 11.8+ (NVIDIA), MPS (macOS 14+), ROCm 5.6+ (AMD) |
| NFR-COMP-005 | Minimum RAM | 16 GB (32 GB recommended) |
| NFR-COMP-006 | Minimum storage | 50 GB free (500 GB+ recommended for video work) |

### 15.4 Scalability

| ID | Metric | Target |
|----|--------|--------|
| NFR-SCALE-001 | Max project videos | 500 per project |
| NFR-SCALE-002 | Max clip candidates | 200 per video |
| NFR-SCALE-003 | Max timeline clips | 1000 per timeline |
| NFR-SCALE-004 | Max timeline tracks | 10 (5 video + 5 audio) |
| NFR-SCALE-005 | Max undos | 100 operations |
| NFR-SCALE-006 | Max export queue | 50 jobs |

---

## 16. Traceability Matrix

| SRS Section | PRD Reference | Vision Reference |
|-------------|---------------|-----------------|
| §3 HAL | PRD-PERF-001 through PRD-PERF-008 | §3.5 GPU Strategy |
| §4 Storage | PRD-STOR-001 through PRD-STOR-008, F-22 | §3.8 Storage Philosophy |
| §5 Database | PRD-PM-001 through PRD-PM-010 | §3.3 Backend |
| §6 API | All feature domains F-01 through F-22 | §3.3 Backend |
| §7 WebSocket | PRD-PERF-001, PRD-AIP-014 | §3.3 Backend |
| §8 AI Pipeline | F-02, PRD-AIP-001 through PRD-AIP-019 | §5 AI Pipeline, §3.4 AI |
| §9 Plugin | F-17, PRD-PLUG-001 through PRD-PLUG-012 | §3.6 Plugin System |
| §10 Services | All feature domains | §3.3 Backend |
| §11 State Machines | F-02, F-14, F-15, F-16, F-17 | §3.3 Backend |
| §12 Errors | All PRD error sections | §8 Quality Gates |
| §13 Testing | PRD implicit | §8 Quality Gates |
| §14 Security | PRD-SEC-001 through PRD-SEC-004, PRV | §8 Quality Gates, §3.4 |
| §15 NFR | PRD non-functional | §3.7 Performance Targets |

---

## 17. Explicitly Excluded Scope

The following features are explicitly excluded from this SRS and will never be implemented in Local Clip Studio:

| Feature | Rationale |
|---------|-----------|
| User authentication, login, registration | Single-user application; no need |
| Passwords, password management | No users to authenticate |
| OAuth, JWT, session tokens | No auth infrastructure needed |
| Multi-user support | Single user, single machine |
| Team collaboration, workspaces | Personal tool only |
| Organizations | Not applicable |
| Subscription, billing, payment processing | Free, open-source, no monetization |
| Licensing server, license validation | No licensing model |
| User analytics, telemetry, crash reporting | Privacy-first; zero data off-device |
| Cloud storage, cloud rendering | Local-first by design |
| Email verification, password reset | No email infrastructure |
| Notifications (email, push) | Not applicable to single user |
| Customer dashboard, admin panel | Not a SaaS product |
| Role-based access control (RBAC) | No roles, no users |
| Multi-tenant database | Single tenant |
| Affiliate system, referral system | Not applicable |
| Marketplace, app store | Not applicable |
| SaaS infrastructure | The application is not a service |

---

## 18. Quality Gate Checklist

Before this SRS is finalized, the following checks must pass:

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Internal consistency — no contradictory requirements | ⬜ | |
| 2 | Requirement completeness — every PRD feature addressed | ⬜ | |
| 3 | Ambiguity detection — no "should", "preferably", "ideally" | ⬜ | |
| 4 | Missing interfaces — every service has input/output contracts | ⬜ | |
| 5 | Circular dependencies — no circular import patterns | ⬜ | |
| 6 | Performance bottlenecks — every stage has performance targets | ⬜ | |
| 7 | Security risks — path traversal, API key handling, zero telemetry | ⬜ | |
| 8 | Extensibility — plugin interfaces for replaceable components | ⬜ | |
| 9 | Testability — every component has test specification | ⬜ | |
| 10 | Traceability — all requirements trace to Vision → PRD → SRS | ⬜ | |

---

*End of Software Requirements Specification*
