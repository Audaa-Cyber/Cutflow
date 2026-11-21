# Deploy Cutflow

Cutflow uses a static frontend on Vercel and one persistent Docker backend. Video files are uploaded directly to the backend, so they do not pass through Vercel's function request-size limit. Authentication, SQLite projects, Whisper, FFmpeg, and the Node caption renderer run on the backend.

If you have not chosen hosting before: the backend needs a computer that stays online, runs Docker, and keeps its disk across restarts. You can rent a Linux server or choose a container service with persistent storage. The steps below use a Linux server and a DNS hostname you control; the Docker package does not provision or purchase that server. Keep Vercel for the frontend.

The prepared image has passed a real 29.5 MiB upload, transcription, Canvas export, edited subtitles, two-account isolation and restart-persistence test locally. The original reported YouTube URL also passed actual download, transcription, clipping and edited export from the local Docker connection. Generated/edited video durations were verified with ffprobe. See `DEPLOYMENT_READINESS.md` for the exact verified scope and remaining live checks.

## 1. Prepare the backend server

Use a Linux server with Docker Compose, enough disk for source videos and outputs, and at least 4 GB of RAM for initial small-model use. Set a DNS hostname such as `api.your-domain.com` to the server's public address. Allow inbound TCP ports 80 and 443. Start with one Cutflow instance; do not scale replicas or add Uvicorn processes with the local SQLite/worker architecture.

Copy `.env.example` to `.env` and configure:

```dotenv
CUTFLOW_API_HOST=api.your-domain.com
CUTFLOW_API_URL=https://api.your-domain.com
CUTFLOW_ALLOWED_ORIGINS=https://cutflow-fawn.vercel.app
WHISPER_MODEL=base
WHISPER_CPU_THREADS=2
CUTFLOW_MAX_OWNER_ACTIVE_JOBS=2
MAX_ACTIVE_JOBS=4
```

Then run:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
docker compose logs -f cutflow
```

Caddy obtains HTTPS certificates and forwards requests to the private backend port. The backend's maximum video size is controlled by `MAX_UPLOAD_MB`; if another proxy sits in front of Caddy, its upload-size and request-duration limits must also support the chosen size. Caddy does not add a smaller request-body limit in the supplied configuration.

Visit `https://api.your-domain.com/api/health` to confirm the backend is reachable. The Docker health check proves API availability; first-time model download and a full media workflow still need verification.

Keep the `cutflow-data` volume across redeployments. It contains projects, account/password hashes, bearer session hashes, media signing material, uploads, rendered outputs, and model caches. Back it up. `docker compose down` preserves it; **do not use `down -v` when keeping data**.

For local use only:

```sh
docker compose up --build
```

Open `http://localhost:8000`. The frontend served by Docker uses the same origin.

## 2. Connect the Vercel frontend

Set `CUTFLOW_API_URL` in the Vercel project's Production environment to the HTTPS backend origin:

```text
https://api.your-domain.com
```

Do not include `/api`, credentials, or a query string. Add every frontend domain used in production or preview to the backend's `CUTFLOW_ALLOWED_ORIGINS` list. The supplied Vercel configuration builds static assets into `dist`; it no longer deploys media workers or sends videos through Vercel functions.

Redeploy the frontend after setting its backend URL. A Production Vercel build deliberately fails if the backend URL is missing or invalid. A backend running only on your laptop is not a persistent public production backend.

Only `CUTFLOW_API_URL` is embedded in the frontend. AI keys, Blob credentials, session material, and YouTube cookies belong exclusively on the backend.

## 3. Accounts and media access

Visitors register or sign in before creating and managing projects. Each account can access only its projects. Legacy projects with no owner are not exposed to new accounts. The browser keeps the opaque bearer session in session storage; signing out revokes it. Media playback/download URLs use short-lived scoped grants tied to the session, so refresh a project when its media links expire.

The app currently has local password accounts. Email delivery, password recovery, and email verification are not included in this release. Use HTTPS, retain backups, and choose a deployment/authentication provider if those account features are required.

## 4. YouTube configuration

The worker uses current yt-dlp defaults and includes Node for JavaScript challenge support. Some YouTube requests still require an accepted logged-in session or provider-specific token. Export a Netscape `cookies.txt` file for a session permitted to access the video and store it only on the backend.

One way to copy it into the existing private data volume is:

```sh
docker compose exec cutflow mkdir -p /app/data/.secrets
docker compose cp /secure/path/cookies.txt cutflow:/app/data/.secrets/youtube-cookies.txt
docker compose exec cutflow chmod 600 /app/data/.secrets/youtube-cookies.txt
```

Set:

```dotenv
YOUTUBE_COOKIES_FILE=/app/data/.secrets/youtube-cookies.txt
```

Restart/recreate the service after changing environment settings. The worker validates the export format and detects fully expired entries. Validation establishes file usability, not guaranteed YouTube acceptance. If YouTube challenges the server connection, the app reports that clearly and offers local upload. `YOUTUBE_PLAYER_CLIENTS` and `YOUTUBE_PO_TOKEN` are optional operator settings for current supported downloader requirements; they default to blank.

Reference: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies

## 5. Optional Blob backup

Local persistent disk is enough for the prepared deployment. If enabling `BLOB_READ_WRITE_TOKEN`, use a private Blob store on the backend. The application serves cloud media through authenticated backend routes, updates exported artifacts, and deletes associated objects with project deletion. Blob does not replace SQLite persistence or allow multiple backend replicas.

## Release checks

```sh
python -m pip install -r backend/requirements-test.txt
npm ci
python -m unittest discover -s tests -v
npm test
npm run build
docker build -t cutflow .
```

Before directing public users to the release, verify registration/login, isolation between two accounts, a video larger than 25 MB, a permitted YouTube URL, captions on a clip starting later in the source, edited export, quality/subtitle downloads, and project persistence after restarting the backend.

Cancellation may take time during transcription. Retry reports that processing is still stopping until the previous worker exits; pending jobs are removed from the queue when cancelled. When optional cloud storage cannot remove an object, the deletion response and app report the number of files that could not be removed.
