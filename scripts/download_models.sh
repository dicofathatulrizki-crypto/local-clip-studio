#!/usr/bin/env bash
#
# Local Clip Studio — AI Model Downloader
#
# Downloads the default AI models to ~/.localclip/models/.
# Individual models can be selected with command-line arguments.
#
# Usage: bash scripts/download_models.sh [model_name...]
#
# Examples:
#   bash scripts/download_models.sh              # Download all default models
#   bash scripts/download_models.sh whisper      # Only whisper
#   bash scripts/download_models.sh yolo whisper  # Specific models
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Default models to download if no arguments provided
ALL_MODELS=("whisper" "yolo" "embeddings")

download_whisper() {
    local model="${1:-large-v3}"
    info "Downloading Whisper model '${model}'..."
    python3 -c "
from faster_whisper import download_model
download_model('${model}', cache_dir='$HOME/.localclip/models/whisper')
print('Whisper model downloaded successfully')
"
    ok "Whisper model '${model}' ready"
}

download_yolo() {
    local model="${1:-yolov8n-face}"
    info "Downloading YOLO model '${model}'..."
    python3 -c "
from ultralytics import YOLO
model = YOLO('${model}.pt')
model.export(format='onnx')
print('YOLO model downloaded successfully')
"
    ok "YOLO model '${model}' ready"
}

download_embeddings() {
    local model="${1:-all-MiniLM-L6-v2}"
    info "Downloading embeddings model '${model}'..."
    python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('${model}', cache_folder='$HOME/.localclip/models/embeddings')
print('Embeddings model downloaded successfully')
"
    ok "Embeddings model '${model}' ready"
}

# Main
if [ $# -eq 0 ]; then
    SELECTED=("${ALL_MODELS[@]}")
else
    SELECTED=("$@")
fi

for model in "${SELECTED[@]}"; do
    case "$model" in
        whisper|whisperx|stt)
            download_whisper
            ;;
        yolo|yolov8|vision)
            download_yolo
            ;;
        embeddings|embedding)
            download_embeddings
            ;;
        *)
            warn "Unknown model: $model. Skipping."
            ;;
    esac
done

ok "All requested models downloaded."
echo ""
echo "Models stored in: $HOME/.localclip/models/"
ls -lh "$HOME/.localclip/models/" 2>/dev/null || true
