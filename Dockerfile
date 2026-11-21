FROM node:22-bookworm-slim AS renderer
WORKDIR /renderer
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUTFLOW_DATA_DIR=/app/data \
    WHISPER_MODEL=base \
    WORKER_CONCURRENCY=1 \
    HF_HOME=/app/data/models

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl fonts-dejavu-core libstdc++6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt && \
    # Always install the latest yt-dlp so YouTube extractor patches are current
    pip install --upgrade yt-dlp

COPY --from=renderer /usr/local/bin/node /usr/local/bin/node
COPY --from=renderer /renderer/node_modules /app/node_modules

COPY backend /app/backend
COPY frontend /app/frontend
COPY README.md /app/README.md

RUN useradd --create-home --uid 1000 cutflow && \
    mkdir -p /app/data/uploads /app/data/outputs && \
    chown -R cutflow:cutflow /app/data
USER cutflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=4)" || exit 1
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1 --timeout-graceful-shutdown 30"]
