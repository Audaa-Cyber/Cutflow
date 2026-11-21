"""Validated downloader configuration and user-facing failures without credentials."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse


PROVIDER_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
}


def validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a public YouTube or Vimeo video URL.") from exc
    host = (parsed.hostname or "").lower()
    if (parsed.scheme not in {"http", "https"} or host not in PROVIDER_HOSTS
            or parsed.username is not None or parsed.password is not None
            or port not in {None, 80, 443}):
        raise ValueError("Enter a public YouTube or Vimeo video URL without credentials or a custom port.")
    return host


def prepare_cookie_file(data_directory: Path, contents: str) -> Path:
    """Validate Netscape export structure before writing private operator credentials."""
    if "\n" not in contents and "\\n" in contents:
        contents = contents.replace("\\n", "\n").replace("\\t", "\t")
    valid = False
    usable = False
    for line in contents.splitlines():
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif not line.strip() or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 7:
            raise ValueError("YouTube cookies must be a Netscape cookies.txt export, not a browser Cookie header.")
        domain = columns[0].lstrip(".").lower()
        if domain not in {"youtube.com", "google.com", "www.youtube.com", "www.google.com"}:
            continue
        try:
            expires = int(columns[4])
        except ValueError as exc:
            raise ValueError("The YouTube cookies export has an invalid expiry field. Export a fresh cookies.txt file.") from exc
        valid = True
        usable = usable or expires == 0 or expires > time.time()
    if not valid:
        raise ValueError("The cookies file contains no YouTube session entries. Export cookies while signed into YouTube.")
    if not usable:
        raise ValueError("The YouTube cookies have expired. Export a fresh cookies.txt file on the video worker.")
    directory = data_directory / ".secrets"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "youtube-cookies.txt"
    # Open with mode 0600 from creation rather than temporarily using default permissions.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(contents)
    path.chmod(0o600)
    return path


def configured_cookie_file(data_directory: Path) -> Path | None:
    source = os.getenv("YOUTUBE_COOKIES_FILE", "").strip()
    if source:
        path = Path(source)
        if not path.is_file():
            raise ValueError("The configured YouTube cookies file is unavailable on the video worker.")
        return prepare_cookie_file(data_directory, path.read_text(encoding="utf-8"))
    contents = os.getenv("YOUTUBE_COOKIES", "").strip()
    if not contents:
        return None
    if not any(line.strip() and not line.strip().startswith("#") for line in contents.splitlines()):
        return None
    return prepare_cookie_file(data_directory, contents)


class QuietDownloadLogger:
    """Do not print raw provider failures containing private request context."""

    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def build_download_options(destination: Path, max_bytes: int, *, cookie_file: Path | None = None) -> dict:
    options = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(destination / "source.%(ext)s"),
        "noplaylist": True,
        "max_filesize": max_bytes,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "js_runtimes": {"node": {}},
        "logger": QuietDownloadLogger(),
    }
    if cookie_file:
        options["cookiefile"] = str(cookie_file)
    clients = [part.strip() for part in os.getenv("YOUTUBE_PLAYER_CLIENTS", "").split(",") if part.strip()]
    if any(not re.fullmatch(r"[a-z0-9_]+", client) for client in clients):
        raise ValueError("YOUTUBE_PLAYER_CLIENTS must contain comma-separated supported client names.")
    token = os.getenv("YOUTUBE_PO_TOKEN", "").strip()
    if clients or token:
        arguments = {}
        if clients:
            arguments["player_client"] = clients
        if token:
            arguments["po_token"] = [token]
        options["extractor_args"] = {"youtube": arguments}
    return options


def safe_download_error(error: object) -> str:
    description = str(error).lower()
    if any(marker in description for marker in ("not a bot", "sign in to confirm", "login required")):
        return ("YouTube requires verification for this download. The video worker needs a current "
                "YouTube cookies session or a permitted download connection. You can upload the video file instead.")
    if any(marker in description for marker in ("private video", "members-only", "age-restricted", "video unavailable")):
        return "This video is unavailable or requires account access. Use an accessible video or upload the file instead."
    if "requested format" in description or "no video formats" in description:
        return "The source did not offer a downloadable video format. Refresh the worker's downloader configuration or upload the file."
    if "too large" in description or "max_filesize" in description:
        return "The downloaded video exceeds the configured size limit. Use a smaller video."
    if "timed out" in description or "timeout" in description:
        return "The video download timed out. Retry or upload the video file."
    return "The source video download failed. Check that the link is public, retry, or upload the video file."
