# Cutflow deployment readiness and error investigation

Reviewed: 2026-11-21

Deployment: https://cutflow-fawn.vercel.app/

Audience: public.

Current status: **registration, login, logout and account-based project access were removed at the user's request. The app now uses a shared workspace.**

The user approved end-to-end fixes and selected Docker deployment preparation. Application and deployment changes are implemented in the working tree. The existing public Vercel deployment has not been changed.

## Account-removal update

- Removed the account modal, disabled initial app shell, sign-out controls, session storage handling, bearer headers, authentication endpoints, ownership filtering and signed account media links.
- Projects, previews, exports, subtitles, retries, cancellation and deletion now work without signing in. All visitors share the deployment's project library. Legacy project data remains available without exposing former owner identifiers.
- Global processing capacity, downloader configuration, media cleanup and caption/rendering fixes remain in place. No project/database files were deleted during this code change.
- Post-removal verification passed: **153 backend tests**, **22 frontend/build tests**, static frontend build, JavaScript/Python syntax checks and `git diff --check`.
- The earlier Docker image and real-media results below predate account removal; rebuild the image when deploying this change. Vercel Container support is available, but the current deployment configuration still targets a static frontend and separate backend.

The earlier authentication/ownership test results below describe the previous release and no longer represent the current access policy.

## Current verification after fixes

- **157 backend tests passed**, including authentication, ownership, worker cancellation/retry, media/storage regressions, generated word-timestamp validity, actual sound-effect export duration and downloader configuration.
- **26 frontend/build tests passed**, including a 26 MB upload directed to the backend, HTTP 413 errors, Studio opening/timing/audio reopening, account changes, and cloud-cleanup warnings.
- `npm run build`, `npm run check` and `git diff --check` passed.
- The production Docker image built successfully with Python 3.11, Node 22, FFmpeg, `@napi-rs/canvas`, faster-whisper and yt-dlp 2026.10.26. Production Docker Compose configuration validation passed.
- Installed private Blob upload/download/delete interfaces were inspected and match the integration. Actual cloud-object operations still require a configured private Blob store and credentials.

### Real media workflow from the final Docker image

An isolated localhost instance used a dedicated verification data volume, not the user's local project database or production storage.

- A valid **30,888,296-byte video (29.5 MiB)** uploaded successfully through `/api/jobs/upload`.
- Real spoken audio was transcribed with the tiny Whisper model. A clip spanning source times **69.1–80.56 seconds** contained 28 timestamped words.
- Initial and edited exports used the **Canvas renderer**, rather than silently falling back to ASS.
- ffprobe confirmed that both generated and edited master videos stop at the selected clip's end, including when sound-effect inputs are present.
- Clean preview and 480p quality export retained audio. Edited subtitles contained the changed text.
- A second account could not list, read, cancel, retry, delete or bulk-delete the first account's project. Ungranted media was rejected; scoped preview/download grants worked.
- Project state, sessions, edited timelines and rendered media survived a container restart.
- Owner deletion and session revocation succeeded.

Local diagnostics and reports are retained in the ignored `scratch` directory: `backend-final.log`, `frontend-green.log`, `docker-build-final.log`, `container-e2e.log`, and `container-e2e/report.json`.

### Independent review and follow-up fixes

One independent review found no critical issues and two important retry defects. Regression tests reproduced both; the fixes then passed the complete backend suite.

- Pending worker Futures are cancelled. A retry is refused while the previous processing attempt or export is still stopping, preventing duplicate queued/running attempts.
- Retry preserves prior cloud artifact locations in the persisted cleanup inventory, so later deletion includes older files.
- Studio retains and suspends its reusable Web Audio mixer rather than closing the permanent video audio connection.
- Failed cloud deletions return a safe count and are shown to the owner in the frontend.
- Real YouTube integration exposed two further renderer/timeline issues. Generated zero-length words now receive valid bounded spans on consistent second/millisecond clocks, and FFmpeg source/output limits prevent sound-effect inputs from extending the video beyond its requested clip duration. Both regressions failed before the fixes and passed afterward; the full synthetic Docker workflow was rerun against the corrected image.

### YouTube verification

The original reported video `mRD0-GxqHVo` passed the **full source-import workflow** from the final local Docker image without adding cookie credentials:

- The 235.061-second source downloaded and was transcribed successfully.
- A 15-second clip containing 23 timestamped words rendered with Canvas.
- The downloaded source remained available for an edited Studio export; updated subtitles contained the edited text.
- ffprobe confirmed the initial and edited videos stop at the selected clip end, including sound effects.
- The isolated test project was deleted and its test session revoked after verification.

Evidence: `scratch/youtube-workflow.log` and `scratch/container-e2e/youtube-report.json`.

This establishes local access only. The eventual hosted worker's connection may still receive a YouTube verification challenge. Cookie format/expiry validation and actionable challenge errors are implemented; cookies do not guarantee acceptance.

### Local-data recovery assessment

An earlier session ran compatibility tests against local storage before isolating it. That may have affected existing local projects. All resumed tests used isolated storage, and the dedicated Docker volume was separate from `data/`.

Read-only SQLite checks found valid databases and two job rows in both the current database and the earlier backup. The recovered copy also contains a `lost_and_found` table, but this does not establish complete recovery of previous projects or their source videos. Recovery copies remain under `scratch/local-data-recovery/`. No automatic replacement of the local database was performed.

## Required for the public website

1. Choose a persistent Linux backend server/container host with Docker, durable storage and adequate RAM. Only one Cutflow instance is supported by the selected SQLite/worker architecture.
2. Configure its API hostname, HTTPS and allowed Vercel origins using `DEPLOYMENT.md`.
3. Set the Vercel Production `CUTFLOW_API_URL` to the actual HTTPS backend origin, then redeploy the static frontend.
4. Repeat the large upload and permitted YouTube workflow from that host. Configure an accepted YouTube session only if that connection requires it.

No public backend server has been selected or provisioned. Password recovery/email verification and multiple replicas remain documented release exclusions.

## Original investigation before approval (historical)

The findings below explain the original failures and the approved work. File line references and statements about missing features describe the pre-fix revision; they are superseded by the verification above.

### Original verification completed

- All 105 existing tests passed with `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
- Python syntax checks passed for all 18 backend and test Python files.
- JavaScript syntax checks passed for frontend and backend JavaScript files.
- A local one-second Node/Skia/FFmpeg export succeeded, producing a 320 x 180 MP4 with video and audio.
- The Docker image was not built: Docker Desktop's engine was not running.
- Full transcription and processing of a real recording on the deployed service have not been verified.
- Local success does not establish that the deployed image includes the same dependencies.

## Readiness findings

### 1. Public API has no authentication or project ownership enforcement

Priority: release blocker for public access.

`backend/app.py:1836` exposes every project through `GET /api/jobs`. Cancel, retry, download, and delete operations do not check an authenticated owner. `backend/app.py:2133` exposes `DELETE /api/jobs`, which clears all jobs, database rows, and media directories.

Impact: any visitor can access other users' projects or disrupt/delete their work. Creating jobs is also unauthenticated; the global active-job cap does not provide per-user quotas.

Proposed work: add authentication and enforce ownership for every job, clip, timeline, and mutation route; restrict bulk deletion appropriately; add per-user limits.

### 2. Caption Studio fails on first open

Priority: release blocker for the advertised editor.

`captionStyleNames` and `PRESET_RECIPES` are declared inside `init()` at `frontend/app.js:593` and `frontend/app.js:614`. `openCaptionStudio()` is outside that scope and references them at `frontend/app.js:1103` and `frontend/app.js:1126`.

Reproduction: loading the unchanged script in a Node VM with minimal DOM mocks and calling `openCaptionStudio()` produced `ReferenceError: captionStyleNames is not defined` at line 1103.

Proposed work: place shared preset data in an accessible module/scope and verify actual Studio opening and preset switching.

### 3. Docker image omits Node rendering dependencies

Priority: release blocker for animated canvas export parity.

`Dockerfile:9` installs Python and FFmpeg but does not install Node/npm, copy the package manifests, or install `@napi-rs/canvas`. `backend/app.py:1374` returns false if Node is unavailable, causing ASS/libass fallback. The Studio UI still describes successful export as Skia parity.

Impact: the deployed container cannot use the same canvas renderer used locally; animated effects and preview/export consistency differ.

Proposed work: package the Node renderer and dependencies in the production image; verify a real export from that image; report the actual rendering mode accurately.

### 4. Job state and workers require a persistent single instance

Priority: release blocker on ephemeral or multiple-instance hosting.

`backend/app.py:281` stores jobs in process memory, `backend/app.py:122` uses local SQLite, and `backend/app.py:327` runs jobs in a thread executor. Restart recovery marks unfinished jobs failed. Blob storage stores media rather than the project registry or queue.

Impact: another instance cannot reliably find newly submitted projects; ephemeral filesystem loss can remove project history; background processing can be interrupted by instance shutdown.

`Dockerfile:6` sets `CUTFLOW_DATA_DIR=/app/data`, overriding the application's automatic `/tmp` fallback. A host that only allows writes under `/tmp` would need configuration changes. That filesystem restriction has not been confirmed for this deployment.

Proposed work: choose and verify a hosting design with durable project state and a reliable worker lifetime. A persistent single container is the smallest architecture change; keeping elastic hosting requires an external database and durable job queue/workers.

### 5. URL-imported projects cannot export Studio edits

Priority: high.

`backend/app.py:1446` downloads the URL source but does not persist the downloaded file as `source_path`. `export_custom_clip()` requires `source_path` at `backend/app.py:1909`.

Reproduction: isolated execution with a URL-source job returned HTTP 400, `Source video file is not available.`

Proposed work: persist and resolve the downloaded source consistently for editing, retries, and exports.

### 6. Caption Studio playback and timeline timestamps disagree

Priority: high.

Generated timeline timestamps are absolute source-video timestamps. The headless renderer uses source start plus frame time. Studio passes the clipped video's zero-based `currentTime` to the renderer at `frontend/app.js:1174` and `frontend/app.js:1399`.

Reproduction: a phrase starting at source time 60 seconds produced zero word boxes at 0.5 seconds and one at 60.5 seconds.

Studio also uses an already caption-burned MP4 as the video underneath its editable caption overlay (`frontend/app.js:1097`).

Proposed work: define and apply a consistent time origin for preview, editing, sound effects, and export; provide a clean video preview underneath editable captions.

### 7. Blob workflows are incomplete when cloud storage is enabled

Priority: high when Blob is enabled.

- Studio rewrites the local MP4 but does not upload the edited video or update its Blob URL (`backend/app.py:1927` through the export response).
- Retry treats a `blob:https://...` source as a local path (`backend/app.py:2110`), returning HTTP 400.
- Frontend subtitle links replace `.mp4` in the video URL (`frontend/app.js:361`, `frontend/app.js:365`) instead of using the supplied subtitle endpoint URLs. The resulting Blob subtitle URLs have no corresponding uploaded files.
- Quality selection appends `resolution` to a Blob CDN URL, which bypasses the backend's variant-rendering endpoint.
- `blob_delete()` is defined but not called during project deletion. Public cloud source/output files remain after local project deletion.

Blob SDK import/API compatibility has not been verified against the deployed package installation.

Proposed work: use explicit backend routes for subtitles and quality variants; upload edited outputs; resolve Blob sources during retry; delete associated cloud objects; verify the SDK integration.

### 8. CI does not provision all required test dependencies

Priority: high for a dependable release gate.

`.github/workflows/ci.yml:21` installs FastAPI, python-multipart, and pytest, but omits Pillow and HTTPX. The workflow also does not install the Node canvas dependency used by renderer tests.

Proposed work: declare and install complete test dependencies, install Node dependencies from the lockfile, and run verification in a clean environment matching production.

## Deployed upload failure

User report: a video of approximately **25 MB** displays `Server temporarily unavailable. Please retry.`

### Confirmed root cause

The deployment's Vercel request layer rejects the upload payload before the Cutflow upload handler runs. The application submits the entire video as multipart data to `/api/jobs/upload`. Increasing `MAX_UPLOAD_MB` cannot raise the hosting platform's request-body limit.

Live diagnostic evidence:

| Request | Result |
| --- | --- |
| `GET /` | HTTP 200, HTML |
| `GET /api/health` | HTTP 200, JSON identifying Cutflow 0.2.0 |
| `POST /api/jobs/upload` with a rejected `.txt` file, 1,198-byte total request | HTTP 400, JSON: `Unsupported video format...` |
| Same rejected `.txt` file, 6,291,630-byte total request | HTTP 413, plain text; `x-vercel-error: FUNCTION_PAYLOAD_TOO_LARGE` |

Large-request response:

```text
Request Entity Too Large

FUNCTION_PAYLOAD_TOO_LARGE
```

The `.txt` diagnostic files are rejected before video-job creation. These requests did not submit videos or create processing jobs.

Large-request Vercel trace ID: `cdg1::c74h5-1795216596730-d2b324566605`.

The deployed frontend contains the same generic fallback message as `frontend/app.js:141`. Non-JSON error responses are reduced to that message, hiding the actual platform error.

### Proposed fix direction, pending approval

- If retaining Vercel for the frontend/API, send large video bytes directly from the browser to suitable object storage using a controlled upload authorization flow. Submit only the resulting source reference and editing settings to the job API.
- Perform media processing on a worker host that supports its duration, CPU, disk, and dependency requirements.
- Alternatively, host the upload API and workers on a persistent container server with verified proxy/body-size limits appropriate for the allowed upload size.
- Display the actual upload-size/platform failure clearly instead of describing it as temporary service unavailability.

## Deployed YouTube-link failure

User-reported video ID: `mRD0-GxqHVo`.

User-reported error:

```text
ERROR: [youtube] mRD0-GxqHVo: Sign in to confirm you're not a bot.
Use --cookies-from-browser or --cookies for authentication.
```

### Confirmed cause and remaining uncertainty

YouTube rejects the downloader's request with an authentication/bot-verification challenge. The failure occurs in source download, before transcription or rendering. The returned yt-dlp message establishes the rejection, but does not distinguish missing cookies, expired cookies, session/IP restrictions, or additional current YouTube client requirements.

`download_source()` at `backend/app.py:415` uses yt-dlp. It passes a cookies file only when `_YT_COOKIES_PATH` exists. That path is created at process startup from the `YOUTUBE_COOKIES` environment variable (`backend/app.py:92`). It forces the `web_embedded` and `web` player clients (`backend/app.py:446`).

The Dockerfile upgrades yt-dlp during image build; the installed version and accepted session on the live deployment have not been verified. Cookie values and deployed secrets were not inspected or collected. No live YouTube download was initiated during this investigation.

The user is not sure whether `YOUTUBE_COOKIES` is configured for Vercel's Production environment. Its presence and validity therefore remain unverified; the investigation does not claim it is definitely missing.

### Proposed investigation/fix direction, pending approval

- Verify the deployed yt-dlp version and whether a valid cookies configuration actually reaches the downloader, without exposing cookie contents.
- Validate current supported YouTube client/authentication requirements and any necessary JavaScript-runtime or token support. Reassess the forced client selection against that evidence.
- Use a worker host with a reliable permitted download path; cloud-origin requests may remain challenged even when cookies are present.
- Provide an actionable YouTube authentication error and retain local video upload as an alternative.
- Do not promise that adding cookies alone will resolve all YouTube bot challenges. `--cookies-from-browser` requires a browser profile available to the downloader; a deployment container does not inherit the user's local browser session.

Reference guidance supplied by the error:

- https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
- https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies

## Original approval boundary (satisfied)

The user subsequently approved end-to-end implementation and selected Docker deployment preparation. The prepared application/image have been verified locally as recorded above; public hosting and live provider credentials remain external setup requirements.
