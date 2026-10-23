# Cutflow

Turn long videos into short-form clips.

Cutflow MVP accepts an uploaded video or a supported public video URL, analyzes the speech, proposes clips using a selected content template, and renders downloadable vertical videos with captions.

## MVP scope

- Upload local video files or submit supported public video URLs.
- Choose an editing template: Podcast, Educational, Storytelling, Funny Moments, or Gaming Highlights.
- Transcribe speech with faster-whisper.
- Rank candidate moments using transcript signals and template-specific heuristics.
- Render vertical, square, or landscape MP4 clips with burned-in subtitles using FFmpeg.
- Preview and download rendered clips.
- No social publishing, live-stream processing, or free-form prompt-driven editing in this version.

## Run locally with Docker

Requirements: Docker and Docker Compose.

```bash
docker compose up --build
```

Open http://localhost:8000. On first run, faster-whisper downloads the selected model, so initial transcription can take a while. Set `WHISPER_MODEL=base` for a smaller/faster model or `small` for a quality/speed balance.

## Run without Docker

Install FFmpeg and Python 3.11+, then:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

## Notes

- The first MVP uses transcript-driven, template-specific ranking. It does not claim to predict virality and does not yet use a hosted LLM.
- Public URL ingestion is implemented through yt-dlp. Only submit videos you own or have permission to process, and respect the source platform's terms.
- The service is intended for trusted local development. Before public deployment, add authentication, per-user quotas, isolated media workers, malware scanning, SSRF protections for URL ingestion, persistent job storage, and object storage.
- FFmpeg and faster-whisper are the core processing components. Video processing consumes CPU, memory, and disk; do not expose an unprotected instance to the public internet.

## Architecture

- `backend/app.py`: FastAPI API, job state, transcription, candidate ranking, subtitle generation, and rendering.
- `frontend/`: responsive single-page workspace.
- `Dockerfile` / `docker-compose.yml`: reproducible local runtime.
