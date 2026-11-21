# Public deployment fixes implementation plan

> **For agentic workers:** Use subagent-driven-development or executing-plans to implement the assigned tasks. The user approved the investigation and end-to-end fixes and selected a prepared Docker deployment for the persistent backend.

**Goal:** Make Cutflow's public frontend work with a persistent authenticated media backend, including large uploads, editable captions, and reliable export/storage behavior.

**Architecture:** Vercel serves the frontend as static assets. The browser calls a configurable HTTPS Docker backend directly, so video bytes bypass Vercel's function payload limit. One persistent backend instance owns SQLite state and the bounded worker pool. User accounts and bearer sessions protect project APIs; short-lived, scoped media grants allow video playback and downloads. Local same-origin Docker use remains supported.

**Tech stack:** Existing FastAPI/SQLite, Python standard-library authentication, Node canvas renderer, FFmpeg, yt-dlp, Docker Compose, static JavaScript frontend.

**Spec:** `DEPLOYMENT_READINESS.md`, approved by the user. Their additional infrastructure choice is to prepare Docker deployment rather than assume an existing server. Provisioning a new hosted server is not part of that choice.

## Global constraints

- Preserve the six clip templates and all 18 caption presets.
- Protect public job data and mutations with ownership checks; do not serve raw public Blob URLs for private user media.
- Keep browser API requests independent of Vercel's video payload limit.
- Keep durable SQLite and uploads/outputs on a persistent Docker volume; enforce one application process for the SQLite/in-memory worker design.
- Do not expose secret values in tools, frontend config, reports, or logs.
- YouTube access is an external requirement: improve supported downloader configuration, validate cookies, and report challenges honestly; do not claim cookies guarantee access.
- Do not deploy against an unknown backend URL or invent cloud credentials.
- Preserve existing tests where behavior is unchanged; add behavioral regressions for each fixed failure.

## Review focus

- A second account cannot list, export, cancel, retry, or delete another account's jobs.
- A video larger than 25 MB goes directly to the backend, with useful errors and upload progress.
- Studio correctly previews a clip starting at source time 60 seconds and edits a clean video layer.
- Cloud source resolution, retry, edited MP4, subtitle/quality downloads, and deletion remain consistent.
- Restarts, failed downloads, and cancellation do not leave unsafe credentials or falsely completed output.

### Task 1: Persistent backend authentication and project access

Files: `backend/auth.py`, selected authentication/job registry/CRUD sections of `backend/app.py`, `tests/test_auth.py`, existing API test fixtures where required.

Interfaces: `/api/auth/register`, `/api/auth/login` accept JSON `{email,password}` and return `{token,user:{id,email}}`; `/api/auth/me` returns the user; `/api/auth/logout` revokes the bearer session. Authenticated requests use `Authorization: Bearer <token>`. Media download/preview routes accept a short-lived scoped `media_token` grant generated in public job responses. `/api/health` remains public. CORS origins come from `CUTFLOW_ALLOWED_ORIGINS`. Use persistent SQLite users/sessions and an authenticated request context for job creation. Public job responses hide source/blob storage locations. Bulk deletion affects only the authenticated owner's jobs. Add bounded per-owner job quotas.

- [x] Add failing real HTTP tests for login, ownership, bearer expiry/logout, scoped media grants, cross-origin requests, and owner-only deletion.
- [x] Implement auth with salted password hashing, opaque hashed sessions, and persistent signing material.
- [x] Integrate authorization without giving unauthenticated public callers access to legacy jobs. Maintain explicit internal/local-test behavior for direct helper calls.
- [x] Verify tests and report interfaces and compatibility decisions.

### Task 2: Media pipeline, source handling, clean preview and exports

Files: media/source/render/process/export sections of `backend/app.py`, `backend/media_storage.py` if useful, `tests/test_media_workflows.py`.

Interfaces: clips expose backend-relative `download_url`, `srt_url`, `ass_url`, `preview_url` and `timeline_url`; auth task adds media grants to public responses. `preview_url` points to an uncaptioned, correctly framed clip. Export returns an accurate `renderer` value and updated clip URLs. Sources imported from URL are persisted. Blob sources resolve consistently for retry and Studio export. Cloud storage remains optional and media URLs must pass through protected backend endpoints.

- [x] Add failing tests for URL source persistence, Blob retry/export/delete, exact subtitle timing after local loss, variant routing, clean previews, invalid export bounds/payloads, atomic export and cancellation.
- [x] Implement source/storage resolution, uploads of current cloud artifacts, cleanup and cache invalidation.
- [x] Keep processing/local preview and export on the same source-time convention. Handle full export state atomically and accurately.
- [x] Verify media regressions and existing suite; report any limits.

### Task 3: Public frontend API integration and Caption Studio

Files: `frontend/app.js`, `frontend/api.js` or another small helper, `frontend/index.html`, `frontend/styles.css`, `tests/frontend/*.test.js`.

Interfaces: `window.CUTFLOW_CONFIG.apiBase` is populated by `runtime-config.js` before application scripts; defaults to same origin for Docker. Match Task 1 auth endpoints and session shape. HTTP fetch helper resolves every `/api/` request to the configured backend and attaches bearer tokens. Media URLs from the backend must resolve against that base. Every user-visible API failure is handled without creating fake jobs. Large uploads use the backend URL directly and report progress. Auth UI supports registration/login/logout and hides project state across account changes.

- [x] Add failing behavioral tests for backend-directed 25 MB upload, JSON/plain-text/413 errors, missing configuration, Studio opening and 60-second timeline alignment.
- [x] Implement login/register flow and authenticated API helper using the existing app style.
- [x] Move shared preset data out of `init()` scope; use clean preview source; offset video playback time for captions/SFX; normalize inline editing and active-word highlighting.
- [x] Use explicit subtitle endpoints and backend quality routes; show actual renderer outcome and clear export errors.
- [x] Verify browser-like tests and JavaScript syntax.

### Task 4: YouTube configuration and production packaging

Files: `backend/youtube_source.py`, downloader integration in `backend/app.py`, `Dockerfile`, `docker-compose.yml`, `vercel.json`, `scripts/build_frontend.js`, requirements/test dependencies, CI, `.env.example`, deployment docs.

- [x] Add failing tests for cookies/session configuration, input URL validation, sanitized downloader failures, and safe absent/invalid configuration behavior.
- [x] Use current yt-dlp defaults, configurable cookie file/environment and client overrides, and available JS runtime; make bot challenges actionable without leaking credentials.
- [x] Package Node/npm canvas and FFmpeg in Docker. Honor worker concurrency of one. Persist data and signing/session state, expose health checks and graceful process lifetime.
- [x] Build a static Vercel frontend with a validated public backend base URL and copied fonts; exclude secrets, local data, and developer files.
- [x] Install complete CI dependencies and execute all regression tests plus frontend build.
- [x] Document the exact Docker/TLS/backend URL configuration and environment needed for redeployment.

### Task 5: Integration verification and readiness update

- [x] Run the complete Python and JavaScript test suites.
- [x] Build static frontend; verify all imported assets and no secret config.
- [x] Build/run Docker if Docker engine can be started; check health, two-account isolation, large local upload, clean preview, edited export and restart persistence with synthetic/real local media.
- [x] Review combined changes and fix material issues.
- [x] Update `DEPLOYMENT_READINESS.md` with verified results and remaining external requirements; do not claim the public URL changed unless deployed and checked.

## Progress and rulings

- User approval: implementation and end-to-end fixes authorized; Docker deployment preparation selected.
- Ruling: static Vercel frontend plus direct persistent backend avoids payload caps and instance-local job loss without introducing a cloud database/queue before a host is chosen.
- Ruling: tests and reversible code fixes proceed without repeating approval; external provider credentials and server provisioning remain user-supplied resources.

- Completion (2026-11-21): Docker-preparation tasks verified with 157 backend tests, 26 frontend/build tests, real 29.5 MiB upload and original YouTube download/edit/export, accurate durations and restart persistence. Public hosting/HTTPS/backend URL and actual cloud credentials remain external setup requirements; no live redeployment performed.
