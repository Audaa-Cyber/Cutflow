# Cutflow

Turn long videos into short-form clips.

Cutflow accepts an uploaded video or a supported public video URL, analyzes speech and scene changes, proposes clips using a selected content template, and renders downloadable short-form videos with captions. Projects are stored in SQLite so the project library survives a container restart.

## MVP scope

- Upload local video files or submit supported public video URLs.
- Choose an editing template: Podcast, Educational, Storytelling, Funny Moments, or Gaming Highlights.
- Transcribe speech with faster-whisper.
- Rank candidate moments using transcript signals, template-specific heuristics, and FFmpeg scene-change cues.\n- Add an optional natural-language editing brief; when an OpenAI-compatible chat-completions provider is configured, use it to rerank candidates and explain clip selections.\n- Persist job metadata in SQLite and recover the project library across restarts.
- Render vertical, square, or landscape MP4 clips with burned-in subtitles using FFmpeg.
- Preview and download rendered clips.
- No social publishing, live-stream processing, or free-form prompt-driven editing in this version.

## Optional AI editing briefs\n\nCopy `.env.example` to `.env` and set `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` to an OpenAI-compatible chat-completions endpoint. The base URL should include its API prefix if the provider uses one (for example, `/v1`). Keep API keys in `.env` or your deployment secret store, never in frontend code. When prompt reranking is enabled, the editing brief, a transcript excerpt, and candidate clip text are sent to that configured provider; the source video itself remains in the Cutflow instance. If the provider is not configured or a request fails, Cutflow falls back to the automatic template ranking and displays a warning. Without provider credentials, the editing-brief field is informational and heuristic selection remains fully usable.\n\n## Run locally with Docker

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

- Cutflow combines transcript-based scoring with lightweight FFmpeg scene-change cues. Optional AI reranking is used only when a provider is configured and an editing brief is supplied. Neither heuristic scores nor AI selections guarantee virality.
- Public URL ingestion is implemented through yt-dlp. Only submit videos you own or have permission to process, and respect the source platform's terms.
- The service is intended for trusted local development. Before public deployment, add authentication, per-user quotas, isolated media workers, malware scanning, stronger SSRF protections for URL ingestion, per-user authorization, and managed object storage. The current SQLite database is suitable for a single-instance local deployment, not horizontal scaling.
- FFmpeg and faster-whisper are the core processing components. Video processing consumes CPU, memory, and disk; do not expose an unprotected instance to the public internet.

## Architecture

- `backend/app.py`: FastAPI API, SQLite-backed job state, transcription, scene detection, candidate ranking, optional AI reranking, subtitle generation, and rendering.\n- `tests/test_cutflow.py`: unit tests for templates, candidate ranking, title generation, and AI fallback behavior.
- `frontend/`: responsive single-page workspace.
- `Dockerfile` / `docker-compose.yml`: reproducible local runtime.
\n## Checks\n\nGitHub Actions runs Python compilation, backend unit tests, and JavaScript syntax checks on pushes and pull requests. The media pipeline still needs a local end-to-end run with a real source video and FFmpeg/faster-whisper installed.\n