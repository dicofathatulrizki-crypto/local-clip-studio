#!/usr/bin/env bash
#
# Local Clip Studio — Development Server
#
# Starts both the backend (FastAPI) and frontend (Vite) dev servers.
# Press Ctrl+C to stop both.
#
# Usage: bash scripts/dev.sh
#    or: make dev
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting Local Clip Studio (Development Mode)${NC}"
echo ""

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup first...${NC}"
    bash scripts/setup.sh
fi

# Activate virtual environment
source venv/bin/activate

# Function to clean up child processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend (FastAPI) on http://127.0.0.1:8765${NC}"
python -m backend.main --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
if command -v bun &>/dev/null; then
    echo -e "${GREEN}Starting frontend (Vite + bun) on http://localhost:5173${NC}"
    bun run dev &
    FRONTEND_PID=$!
elif [ -f "package.json" ]; then
    echo -e "${GREEN}Starting frontend (Vite + npm) on http://localhost:5173${NC}"
    npm run dev &
    FRONTEND_PID=$!
else
    echo -e "${YELLOW}No frontend package.json found. Skipping frontend.${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Local Clip Studio is running${NC}"
echo -e "${GREEN}  Backend:  http://127.0.0.1:8765${NC}"
echo -e "${GREEN}  Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}  API Docs: http://127.0.0.1:8765/api/docs${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for any child to exit
wait
