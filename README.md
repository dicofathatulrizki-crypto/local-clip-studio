# Local Clip Studio

A local-first, AI-powered video editing application that transforms long-form videos into short-form vertical clips automatically. Inspired by OpusClip, CapCut Desktop, and DaVinci Resolve.

> **This is a personal-use tool.** It runs entirely on your own machine. No cloud, no accounts, no subscriptions. All AI processing is done locally with open-weight models.

---

## Features

- **🎬 Video Import** — Import MP4, MOV, MKV, AVI, WebM. Drag & drop, batch import, YouTube URL
- **🧠 AI Analysis** — Speech-to-text, speaker diarization, scene detection, hook detection, quality scoring
- **✂️ Auto Clip Generation** — AI-powered clip extraction with smart trimming and ranking
- **🎥 Timeline Editor** — Multi-track timeline with waveform, split/trim, keyboard shortcuts
- **🎞 Smart Reframe** — AI-driven crop from horizontal to vertical (9:16, 1:1, 4:5)
- **💬 Captions** — Animated, karaoke-style, multi-language
- **📦 Export** — MP4, MOV, WebM, SRT, VTT, ASS, EDL, XML

## Quick Start

### Prerequisites

- **Python 3.11+**
- **FFmpeg 6.0+** (for video processing)
- **Node.js 20+** (for frontend development)
- **bun** (recommended) or npm

### One-Click Setup

```bash
bash scripts/setup.sh
```

This will:
- Create a Python virtual environment
- Install all backend dependencies
- Install all frontend dependencies
- Create the application directory (`~/.localclip/`)
- Generate a default configuration

### Development

Start both backend and frontend simultaneously:

```bash
make dev
```

Or start them separately:

```bash
# Backend (http://127.0.0.1:8765)
python -m backend.main --reload

# Frontend (http://localhost:5173)
bun run dev
```

## Architecture

```
frontend/       → React + TypeScript SPA (Vite)
backend/        → Python FastAPI server
  ├── api/      → HTTP routes + middleware
  ├── services/ → Business logic orchestration
  ├── domain/   → Pure business entities (no framework dependencies)
  └── infrastructure/
      ├── database/    → SQLAlchemy 2.0 + SQLite
      ├── hal/         → Hardware Abstraction Layer (GPU)
      ├── ffmpeg/      → FFmpeg subprocess management
      ├── plugins/     → Plugin system for AI providers
      ├── queue/       → Celery background jobs
      ├── websocket/   → Real-time event streaming
      └── logging/     → Structured JSON logging
docker/         → Docker Compose for containerized deployment
scripts/        → Setup and dev helper scripts
tests/          → Unit + integration + E2E tests
docs/           → Vision, PRD, SRS, Architecture, API, DB design
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS 4, shadcn/ui |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite (SQLAlchemy 2.0, Alembic) |
| AI Runtime | PyTorch, ONNX Runtime |
| AI Models | WhisperX, YOLOv8, Qwen/Llama, PySceneDetect |
| Task Queue | Celery (filesystem broker) |
| Video | FFmpeg 6.0+ |
| GPU | CUDA, Apple Metal, ROCm, CPU fallback |

## Project Status

Currently in **Phase 1: Foundation** — building the core infrastructure.

## License

MIT — For personal use only.
