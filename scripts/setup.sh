#!/usr/bin/env bash
#
# Local Clip Studio — Environment Setup Script
#
# Usage: bash scripts/setup.sh
#
# Sets up the complete development environment including:
#   - Python virtual environment
#   - Backend dependencies (Python packages)
#   - Frontend dependencies (Node packages)
#   - Pre-commit hooks
#   - Application directory structure
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ─── Colors ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── Pre-checks ──────────────────────────────────────────────────────────

info "Checking prerequisites..."

# Python 3.11+
PYTHON_VERSION=$(python3 --version 2>/dev/null || python --version 2>/dev/null || echo "none")
if [[ $PYTHON_VERSION == *"3.11"* || $PYTHON_VERSION == *"3.12"* ]]; then
    ok "Python: $PYTHON_VERSION"
else
    error "Python 3.11+ is required. Found: $PYTHON_VERSION"
    error "Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi

# Python package manager
if command -v pip3 &>/dev/null; then
    PIP=pip3
elif command -v pip &>/dev/null; then
    PIP=pip
else
    error "pip not found. Install pip for Python 3."
    exit 1
fi
ok "Package manager: $PIP"

# Node.js (for frontend)
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    ok "Node.js: $NODE_VERSION"
else
    warn "Node.js not found. Frontend development requires Node.js 20+."
fi

# FFmpeg
if command -v ffmpeg &>/dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -1)
    ok "FFmpeg: $FFMPEG_VERSION"
else
    warn "FFmpeg not found. Install FFmpeg 6.0+ for video processing."
    warn "  macOS: brew install ffmpeg"
    warn "  Ubuntu: sudo apt install ffmpeg"
    warn "  Windows: choco install ffmpeg"
fi

# ─── Backend Setup ────────────────────────────────────────────────────────

info "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtual environment created at ./venv"
else
    ok "Virtual environment already exists at ./venv"
fi

# Activate virtual environment
source venv/bin/activate

info "Installing backend dependencies..."
$PIP install --upgrade pip setuptools wheel
$PIP install -e ".[dev]"
ok "Backend dependencies installed"

# ─── Frontend Setup ───────────────────────────────────────────────────────

if command -v bun &>/dev/null; then
    info "Installing frontend dependencies with bun..."
    cd "$PROJECT_DIR"
    bun install
    ok "Frontend dependencies installed"
elif [ -f "package.json" ]; then
    info "Installing frontend dependencies with npm..."
    npm install
    ok "Frontend dependencies installed"
fi

# ─── Application Directory ────────────────────────────────────────────────

info "Creating application data directories..."
python3 -c "
from pathlib import Path
dirs = [
    Path.home() / '.localclip' / 'config',
    Path.home() / '.localclip' / 'projects',
    Path.home() / '.localclip' / 'models',
    Path.home() / '.localclip' / 'cache',
    Path.home() / '.localclip' / 'logs',
    Path.home() / '.localclip' / 'temp',
    Path.home() / '.localclip' / 'exports',
    Path.home() / '.localclip' / 'plugins',
]
for d in dirs:
    d.mkdir(parents=True, exist_ok=True)
    print(f'  Created: {d}')
"
ok "Application directories created"

# ─── Configuration ────────────────────────────────────────────────────────

CONFIG_FILE="$HOME/.localclip/config/settings.json"
if [ ! -f "$CONFIG_FILE" ]; then
    info "Creating default configuration..."
    python3 -c "
from backend.config.defaults import *
import json
defaults = {
    'storage': {
        'app_directory': str(DEFAULT_STORAGE_PATH),
        'max_project_size_gb': DEFAULT_MAX_PROJECT_SIZE_GB,
        'max_cache_size_gb': DEFAULT_MAX_CACHE_SIZE_GB,
    },
    'gpu': {
        'backend': DEFAULT_GPU_BACKEND,
        'memory_limit_percent': DEFAULT_GPU_MEMORY_LIMIT_PERCENT,
        'enable_cpu_fallback': DEFAULT_ENABLE_CPU_FALLBACK,
    },
}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(defaults, f, indent=2, default=str)
"
    ok "Default configuration created at $CONFIG_FILE"
else
    ok "Configuration already exists at $CONFIG_FILE"
fi

# ─── Environment File ────────────────────────────────────────────────────

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok ".env file created from .env.example"
else
    ok ".env file already exists"
fi

# ─── Pre-commit Hooks ────────────────────────────────────────────────────

if command -v pre-commit &>/dev/null; then
    info "Installing pre-commit hooks..."
    pre-commit install 2>/dev/null || true
fi

# ─── Summary ──────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}  Local Clip Studio — Setup Complete${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Backend:   cd $PROJECT_DIR && source venv/bin/activate && python -m backend.main"
echo "  Frontend:  bun run dev  (or npm run dev)"
echo "  Both:      make dev"
echo ""
echo "  Open http://localhost:5173 in your browser."
echo ""
