# Local Clip Studio — Backend Docker Image
#
# Build:   docker build -f docker/Dockerfile -t localclip-backend .
# Run:     docker run -p 8765:8765 -v ~/.localclip:/home/user/.localclip localclip-backend

FROM python:3.11-slim-bookworm AS base

# ─── System Dependencies ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ─── Application ─────────────────────────────────────────────────────────
WORKDIR /app

COPY pyproject.toml ./
COPY backend/ backend/

RUN pip install --no-cache-dir -e .

# ─── Runtime ─────────────────────────────────────────────────────────────
EXPOSE 8765

ENV LOCALCLIP_STORAGE_PATH=/home/user/.localclip
ENV LOCALCLIP_HOST=0.0.0.0  # Docker requires bind to all interfaces

# GPU passthrough (NVidia)
# Run with: --gpus all

VOLUME ["/home/user/.localclip"]

ENTRYPOINT ["python", "-m", "backend.main"]
CMD ["--host", "0.0.0.0", "--port", "8765"]
