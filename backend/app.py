from __future__ import annotations

import json
from functools import lru_cache
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.captions import ass as ass_engine
from backend.captions.presets import PRESETS as CAPTION_PRESETS
from backend.captions.spec import CaptionSpec, resolve_headline_font
from backend.captions.timeline import (
    KineticTimeline,
    WordToken,
    build_kinetic_timeline,
    build_word_token,
    estimate_syllables,
)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = Path(os.getenv("CUTFLOW_DATA_DIR", ROOT / "data"))
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
for directory in (UPLOADS, OUTPUTS, FRONTEND, FONTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def ensure_ffmpeg_path():
    if not shutil.which("ffmpeg"):
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        winget = local_app / "Microsoft" / "WinGet" / "Packages"
        if winget.exists():
            for p in winget.glob("**/ffmpeg.exe"):
                os.environ["PATH"] = str(p.parent) + os.pathsep + os.environ.get("PATH", "")
                break


ensure_ffmpeg_path()

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "1024")) * 1024 * 1024
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", str(3 * 60 * 60)))
MAX_ACTIVE_JOBS = max(1, int(os.getenv("MAX_ACTIVE_JOBS", "4")))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
EXPORT_RESOLUTIONS = {"480", "720", "1080", "2k"}
EXPORT_LOCK = threading.Lock()
DB_PATH = Path(os.getenv("CUTFLOW_DB_PATH", str(DATA / "cutflow.sqlite3")))
AI_BASE_URL = (os.getenv("AI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
AI_MODEL = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be", "vimeo.com", "www.vimeo.com", "player.vimeo.com"}
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
CAPTION_STYLES = {
    key: {
        "label": spec.label,
        "description": spec.description,
        "font": spec.font,
        "headline_font": resolve_headline_font(spec),
        "accent_color": spec.accent,
        "base_color": spec.primary,
        "outline_color": spec.outline,
        "upcoming_color": spec.upcoming,
        "back_color": spec.fill,
        "show_headline": spec.headline != "none",
        "top_banner": spec.headline == "banner",
        "badge_box": spec.caption_box == "per_word" or spec.active == "box",
        "pill": spec.caption_box == "pill",
        "vertical_side": bool(spec.rail),
        "outline": int(spec.outline_width * 4),
        "shadow": int(spec.shadow),
        "glow": int(spec.glow),
        "kinetic_pop": spec.active_pop,
        "caption_box": spec.caption_box,
        "active": spec.active,
        "headline": spec.headline,
        "frame": spec.frame,
        "zone": spec.zone,
        "karaoke": spec.karaoke,
        "uppercase": spec.uppercase,
        "max_words": spec.max_words,
    }
    for key, spec in CAPTION_PRESETS.items()
}

EMOJI_MAP = {
    # Virality & Energy
    "fire": "🔥", "lit": "🔥", "hot": "🔥", "viral": "🔥", "trend": "🔥", "trending": "🔥",
    "crazy": "⚡", "wild": "⚡", "insane": "⚡", "power": "⚡", "shock": "⚡", "shocked": "⚡", "energy": "⚡",
    "boom": "💥", "impact": "💥", "huge": "💥", "massive": "💥",
    # Finance & Success
    "money": "💰", "cash": "💰", "dollar": "💰", "dollars": "💰", "rich": "💰", "revenue": "💰", "profit": "💰", "sales": "💰", "crypto": "💰", "bitcoin": "💰", "paid": "💰",
    "win": "🏆", "winner": "🏆", "champion": "🏆", "success": "🏆", "best": "🏆", "trophy": "🏆",
    "rocket": "🚀", "growth": "🚀", "scale": "🚀", "fast": "🚀", "moon": "🚀", "launch": "🚀",
    "stats": "📈", "double": "📈", "million": "📈", "billion": "📈",
    "boss": "👑", "king": "👑", "queen": "👑", "leader": "👑",
    # Knowledge & Ideas
    "idea": "💡", "secret": "💡", "tip": "💡", "tips": "💡", "hack": "💡", "trick": "💡",
    "mind": "🧠", "brain": "🧠", "think": "🧠", "smart": "🧠", "genius": "🧠", "iq": "🧠",
    "key": "🔑", "unlock": "🔑", "unlocked": "🔑",
    "target": "🎯", "goal": "🎯", "focus": "🎯", "aim": "🎯",
    # Emotions & Reactions
    "love": "❤️", "heart": "❤️", "favorite": "❤️", "passion": "❤️",
    "laugh": "😂", "funny": "😂", "joke": "😂", "hilarious": "😂", "lol": "😂",
    "look": "👀", "see": "👀", "watch": "👀", "notice": "👀",
    "warning": "⚠️", "mistake": "⚠️", "danger": "⚠️", "stop": "⚠️", "problem": "⚠️", "avoid": "⚠️", "never": "⚠️",
    # Media & Entertainment
    "music": "🎵", "song": "🎵", "beat": "🎵", "dance": "🎵", "sing": "🎵", "tune": "🎵",
    "game": "🎮", "gaming": "🎮", "play": "🎮", "player": "🎮",
    "time": "⏱️", "clock": "⏱️", "hour": "⏱️", "minute": "⏱️", "second": "⏱️",
}

TEMPLATES = {
    "podcast": {
        "label": "Podcast & conversation",
        "description": "Strong opinions, quotable moments, and complete thoughts.",
        "keywords": {"think", "believe", "honestly", "important", "actually", "because", "truth", "mistake", "learned", "experience", "secret", "reason"},
        "hooks": ("the truth is", "here's why", "the problem is", "i realized", "the biggest mistake", "what people don't", "let me explain"),
    },
    "educational": {
        "label": "Educational & how-to",
        "description": "Useful explanations, practical advice, and clear takeaways.",
        "keywords": {"how", "why", "step", "first", "second", "example", "learn", "tip", "method", "because", "important", "solution", "practice"},
        "hooks": ("how to", "here is how", "the reason", "step one", "for example", "the key is", "you need to know"),
    },
    "story": {
        "label": "Storytelling",
        "description": "A setup, a turning point, and a satisfying payoff.",
        "keywords": {"then", "suddenly", "finally", "before", "after", "story", "happened", "realized", "moment", "remember", "never", "unexpected"},
        "hooks": ("i remember", "this happened", "one day", "i never expected", "the moment", "what happened next", "it all started"),
    },
    "funny": {
        "label": "Funny moments",
        "description": "Punchlines, surprise, reactions, and playful exchanges.",
        "keywords": {"funny", "laugh", "joke", "crazy", "wild", "seriously", "imagine", "wait", "what", "no way", "bro", "literally"},
        "hooks": ("no way", "you won't believe", "what just happened", "i can't believe", "wait a minute", "are you serious"),
    },
    "gaming": {
        "label": "Gaming highlights",
        "description": "High-energy reactions, clutch moments, and exciting sequences.",
        "keywords": {"win", "won", "clutch", "kill", "enemy", "team", "let's go", "nice", "no", "watch", "crazy", "one shot", "game"},
        "hooks": ("let's go", "one shot", "watch this", "no way", "last second", "we won", "that was close"),
    },
    "music": {
        "label": "Music & performance",
        "description": "Catchy choruses, beat drops, vocal climaxes, and rhythmic moments.",
        "keywords": {
            "chorus", "verse", "drop", "beat", "melody", "song", "sing", "music", "dance",
            "rhythm", "vibe", "track", "sound", "feel", "yeah", "baby", "love", "heart",
            "night", "life", "time", "away", "hold", "let", "go", "wanna", "gonna", "party",
            "bass", "rock", "flow", "fire", "eyes", "dream", "hands", "world", "oh", "whoa",
            "hey", "alright", "groove", "tune"
        },
        "hooks": (
            "drop the beat", "sing it", "listen to this", "one more time", "everybody",
            "here we go", "can you feel", "put your hands", "turn it up", "all night",
            "don't stop", "make some noise", "let it go", "sing along"
        ),
    },
}

STYLE_PROFILES = {
    "podcast": {
        "eq": "contrast=1.04:saturation=1.06:brightness=0.005",
        "unsharp": "5:5:0.25:3:3:0.0",
        "default_caption": "focus",
        "label": "Studio Natural",
        "description": "Studio warmth with natural skin tones and clean speech focus",
    },
    "educational": {
        "eq": "contrast=1.05:saturation=1.03:brightness=0.012",
        "unsharp": "5:5:0.35:3:3:0.0",
        "default_caption": "linen",
        "label": "Crisp Clarity",
        "description": "Enhanced brightness and edge sharpness for diagrams, slides, and tutorials",
    },
    "story": {
        "eq": "contrast=1.08:saturation=1.06:brightness=-0.004",
        "unsharp": "5:5:0.25:3:3:0.0",
        "default_caption": "align",
        "label": "Cinematic Tone",
        "description": "Cinematic contrast curve and rich warm undertones for dramatic narrative",
    },
    "funny": {
        "eq": "contrast=1.06:saturation=1.12:brightness=0.008",
        "unsharp": "5:5:0.30:3:3:0.0",
        "default_caption": "pop",
        "label": "Punchy Pop",
        "description": "Vibrant color saturation and punchy caption accents for comedic timing",
    },
    "gaming": {
        "eq": "contrast=1.08:saturation=1.16:brightness=0.010",
        "unsharp": "5:5:0.45:3:3:0.0",
        "default_caption": "stack",
        "label": "Vivid Dynamic",
        "description": "Ultra-sharp detail filter and high-saturation pop for gameplay HUD and action",
    },
    "music": {
        "eq": "contrast=1.09:saturation=1.14:brightness=0.004",
        "unsharp": "5:5:0.30:3:3:0.0",
        "default_caption": "evo",
        "label": "Concert Vibrance",
        "description": "Concert stage vibrancy, deep contrast blacks, and soft glowing captions",
    },
}

JOBS: dict[str, dict] = {}
LOCK = threading.RLock()


@contextmanager
def db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def persist_job(job: dict) -> None:
    payload = json.dumps(job, ensure_ascii=False)
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO jobs (id, created_at, updated_at, status, payload) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, status=excluded.status, payload=excluded.payload",
            (job["id"], job["created_at"], job["updated_at"], job["status"], payload),
        )


def load_persisted_jobs() -> None:
    with db_connection() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created_at REAL NOT NULL, updated_at REAL NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL)")
        rows = connection.execute("SELECT payload FROM jobs ORDER BY created_at DESC").fetchall()
    for row in rows:
        try:
            job = json.loads(row["payload"])
            if job.get("status") in {"queued", "processing"}:
                job.update(status="failed", progress=100, stage="Interrupted", message="The server restarted while this job was running. Please submit it again.", error="Processing was interrupted by a server restart.")
                job["updated_at"] = time.time()
                persist_job(job)
            JOBS[job["id"]] = job
        except (ValueError, KeyError, TypeError):
            continue


load_persisted_jobs()
POOL = ThreadPoolExecutor(max_workers=max(2, int(os.getenv("WORKER_CONCURRENCY", "2"))))

app = FastAPI(title="Cutflow", version="0.2.0", description="AI-assisted short-form video clipping workspace")


class URLJob(BaseModel):
    source_url: str
    edit_prompt: str = Field(default="", max_length=1200)
    template: str = "podcast"
    aspect_ratio: str = "9:16"
    clip_count: int = Field(default=3, ge=1, le=8)
    min_duration: int = Field(default=20, ge=10, le=60)
    max_duration: int = Field(default=45, ge=15, le=90)
    caption_style: str = "focus"
    caption_mode: str = "auto"
    caption_prompt: str = Field(default="", max_length=400)
    auto_headline: bool = True
    auto_emoji: bool = False
    uppercase: bool = False
    kinetic_pop: bool = True
    fit_mode: str = "blur"


def update_job(job_id: str, **updates) -> None:
    with LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)
            JOBS[job_id]["updated_at"] = time.time()
            persist_job(JOBS[job_id])


class JobCancelledException(Exception):
    """Raised when an ongoing job is cancelled by the user."""
    pass


CANCELLED_JOBS: set[str] = set()
ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}


def run_command(command: list[str], timeout: int = 900, job_id: str | None = None) -> str:
    if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
        raise JobCancelledException("Processing was cancelled by user.")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if job_id:
        with LOCK:
            ACTIVE_PROCESSES[job_id] = process
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        if job_id:
            with LOCK:
                ACTIVE_PROCESSES.pop(job_id, None)
    if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
        raise JobCancelledException("Processing was cancelled by user.")
    if process.returncode != 0:
        if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
            raise JobCancelledException("Processing was cancelled by user.")
        detail = (stderr or stdout or "Command failed")[-1800:]
        raise RuntimeError(detail)
    return stdout


def probe_video(path: Path) -> dict:
    raw = run_command([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_type,width,height",
        "-of", "json", str(path),
    ], timeout=60)
    data = json.loads(raw)
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("This file does not contain a readable video stream.")
    if duration > MAX_VIDEO_SECONDS:
        raise RuntimeError(f"Video is too long. Maximum supported duration is {MAX_VIDEO_SECONDS // 60} minutes.")
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "duration": duration,
        "size": int(data.get("format", {}).get("size") or path.stat().st_size),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
    }


def download_source(url: str, job_id: str) -> Path:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise RuntimeError("For link imports, use a public YouTube or Vimeo video URL. Direct arbitrary URLs are disabled in this MVP.")
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("URL importing needs yt-dlp. Install the project requirements and restart.") from exc
    destination = UPLOADS / job_id
    destination.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(destination / "source.%(ext)s"),
        "noplaylist": True,
        "max_filesize": MAX_UPLOAD_BYTES,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 2,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)
    candidates = [p for p in destination.glob("source.*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS]
    if not candidates:
        raise RuntimeError("The video download finished, but no supported video file was found.")
    path = max(candidates, key=lambda p: p.stat().st_size)
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise RuntimeError("The downloaded file exceeds the upload size limit.")
    return path


@lru_cache(maxsize=1)
def get_whisper_model():
    """Load Whisper once per server process instead of reloading its weights for every project."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Speech transcription is unavailable. Install backend requirements and restart.") from exc
    return WhisperModel(WHISPER_MODEL, device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"), cpu_threads=max(1, int(os.getenv("WHISPER_CPU_THREADS", str(os.cpu_count() or 4)))), num_workers=1)


def transcribe(path: Path, job_id: str) -> tuple[list[dict], str, str]:
    update_job(job_id, progress=14, stage="Transcribing speech", message="Listening for words and timestamps.")
    model = get_whisper_model()
    segments, info = model.transcribe(str(path), word_timestamps=True, vad_filter=True, beam_size=1, condition_on_previous_text=False)
    words: list[dict] = []
    transcript_parts: list[str] = []
    for segment in segments:
        if job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled":
            raise JobCancelledException("Processing was cancelled by user.")
        segment_text = (segment.text or "").strip()
        if segment_text:
            transcript_parts.append(segment_text)
        if segment.words:
            for word in segment.words:
                token = (word.word or "").strip()
                if token and word.start is not None and word.end is not None:
                    words.append({"start": float(word.start), "end": float(word.end), "word": token})
        elif segment_text:
            tokens = segment_text.split()
            span = max(0.1, float(segment.end) - float(segment.start))
            step = span / max(1, len(tokens))
            for index, token in enumerate(tokens):
                words.append({"start": float(segment.start) + index * step, "end": float(segment.start) + (index + 1) * step, "word": token})
    if not words:
        raise RuntimeError("No speech was detected. Try a video with clearer spoken audio.")
    language = getattr(info, "language", None) or "unknown"
    return words, " ".join(transcript_parts), language


def sentence_groups(words: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        gap = float(word["start"]) - float(current[-1]["end"]) if current else 0.0
        # In speech, split on terminal punctuation; in music/lyrics, also respect natural vocal pauses
        is_break = bool(re.search(r"[.!?][\"'’)]?$", str(word.get("word", "")))) or (gap >= 0.85 and len(current) >= 3)
        current.append(word)
        if is_break:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    # Whisper may return long punctuation-free runs; split them into manageable groups.
    result: list[list[dict]] = []
    for group in groups:
        chunk: list[dict] = []
        for word in group:
            chunk.append(word)
            if len(chunk) >= 22:
                result.append(chunk)
                chunk = []
        if chunk:
            result.append(chunk)
    return result


def get_uncovered_ranges(selected_clips: list[dict], total_duration: float, buffer: float = 5.0) -> list[tuple[float, float]]:
    """Return time intervals (s, e) not covered by selected clips (with buffer), min length 5s."""
    blocked = []
    for c in selected_clips:
        b_start = max(0.0, float(c["start"]) - buffer)
        b_end = min(total_duration, float(c["end"]) + buffer)
        blocked.append((b_start, b_end))
    blocked.sort(key=lambda x: x[0])

    merged_blocked = []
    for b in blocked:
        if not merged_blocked:
            merged_blocked.append(b)
        else:
            prev_s, prev_e = merged_blocked[-1]
            if b[0] <= prev_e:
                merged_blocked[-1] = (prev_s, max(prev_e, b[1]))
            else:
                merged_blocked.append(b)

    uncovered = []
    curr = 0.0
    for b_s, b_e in merged_blocked:
        if b_s > curr:
            uncovered.append((curr, b_s))
        curr = max(curr, b_e)
    if curr < total_duration:
        uncovered.append((curr, total_duration))

    return [(round(s, 2), round(e, 2)) for s, e in uncovered if (e - s) >= 5.0]


def rank_candidates(words: list[dict], template: str, min_duration: int, max_duration: int, video_duration: float, count: int, scene_changes: list[float] | None = None) -> list[dict]:
    config = TEMPLATES[template]
    sentences = sentence_groups(words)
    candidates: list[dict] = []
    target = min(max_duration, max(min_duration + 5, 35))
    for start_index in range(len(sentences)):
        window: list[dict] = []
        for end_index in range(start_index, len(sentences)):
            window.extend(sentences[end_index])
            if not window:
                continue
            start = max(0.0, window[0]["start"])
            end = min(video_duration, window[-1]["end"])
            duration = end - start
            if duration > max_duration:
                break
            if duration >= min_duration:
                text = " ".join(w["word"] for w in window).strip()
                normalized = re.sub(r"[^a-z0-9' ]", " ", text.lower())
                tokens = normalized.split()
                if len(tokens) < 8:
                    continue
                keyword_hits = sum(1 for token in tokens if token in config["keywords"])
                phrase_hits = sum(1 for phrase in config["hooks"] if phrase in normalized)
                hook_bonus = 15 if phrase_hits else 0
                keyword_score = min(24, keyword_hits * 3)
                duration_score = max(0, 15 - abs(duration - target) * 0.55)
                scenes = scene_changes or []

                if template == "music":
                    # Music/performance: detect chorus repetitions and rhythm
                    counts: dict[str, int] = {}
                    for token in tokens:
                        if len(token) > 2:
                            counts[token] = counts.get(token, 0) + 1
                    repeated = sum(cnt - 1 for cnt in counts.values() if cnt > 1)
                    chorus_bonus = min(16, repeated * 3)
                    visual_bonus = min(14, sum(1 for stamp in scenes if start + 0.6 < stamp < end - 0.6) * 2.5)
                    boundary_bonus = 5 if any(abs(stamp - start) <= 1.2 for stamp in scenes) else 0
                    density = len(tokens) / max(1, duration)
                    density_score = min(10, density * 2.5)
                    context_score = 8
                    punctuation_score = 0
                    # Heavy penalty for speech/interview fillers to avoid conversation mismatch
                    filler_penalty = min(28, sum(tokens.count(filler) for filler in ("um", "uh", "erm", "basically", "actually", "literally", "honestly")) * 4)
                    musical_signal = keyword_hits + (2 if phrase_hits else 0) + repeated
                    mismatch_penalty = 18 if musical_signal == 0 else 0
                    score = int(max(25, min(99, 42 + hook_bonus + keyword_score + chorus_bonus + visual_bonus + boundary_bonus + density_score + duration_score + context_score - filler_penalty - mismatch_penalty)))
                else:
                    punctuation_score = min(8, sum(text.count(mark) for mark in "!?") * 2)
                    density = len(tokens) / max(1, duration)
                    density_score = min(12, density * 3)
                    context_score = 10 if text[-1:] in ".!?" else 3
                    visual_bonus = min(8, sum(1 for stamp in scenes if start + 1.5 < stamp < end - 1.5) * 2)
                    boundary_bonus = 4 if any(abs(stamp - start) <= 1.5 for stamp in scenes) else 0
                    filler_penalty = min(10, sum(tokens.count(filler) for filler in ("um", "uh", "erm")) * 2)
                    score = int(max(35, min(99, 40 + hook_bonus + keyword_score + punctuation_score + density_score + duration_score + context_score + visual_bonus + boundary_bonus - filler_penalty)))

                candidates.append({
                    "start": round(start, 2), "end": round(end, 2), "duration": round(duration, 1),
                    "text": text, "score": score, "category": config["label"],
                    "title": make_title(text, template),
                    "visual_cues": sum(1 for stamp in (scene_changes or []) if start < stamp < end),
                })
                # Keep the search bounded; one more sentence may make a better clip.
                if duration >= target:
                    break
    if not candidates:
        # Fallback to safe fixed windows for transcripts without useful sentence boundaries.
        step = max(min_duration, min(max_duration, target))
        start = 0.0
        while start + min_duration <= video_duration and len(candidates) < 40:
            end = min(video_duration, start + step)
            if end - start >= min_duration:
                subset = [w for w in words if w["end"] > start and w["start"] < end]
                text = " ".join(w["word"] for w in subset).strip()
                if text:
                    candidates.append({"start": round(start, 2), "end": round(end, 2), "duration": round(end-start, 1), "text": text, "score": 55, "category": config["label"], "title": make_title(text, template)})
            start += max(10, step * 0.65)
    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict] = []
    for candidate in candidates:
        overlaps = any(candidate["start"] < item["end"] - 5 and candidate["end"] > item["start"] + 5 for item in selected)
        if not overlaps:
            selected.append(candidate)
        if len(selected) >= count:
            break

    # Guaranteed Multi-Clip Generation: If non-overlap filter left us with fewer than count clips
    if len(selected) < count and video_duration >= 5.0:
        while len(selected) < count:
            uncovered_ranges = get_uncovered_ranges(selected, video_duration, buffer=5.0)
            if not uncovered_ranges:
                break
            # Prioritize the largest uncovered gaps
            uncovered_ranges.sort(key=lambda r: (r[1] - r[0]), reverse=True)
            r_start, r_end = uncovered_ranges[0]
            range_dur = r_end - r_start
            clip_dur = min(max_duration, max(min_duration, min(range_dur, target)))
            if clip_dur > range_dur:
                clip_dur = range_dur

            # 1. Try to find an existing speech candidate that fits completely within this uncovered range
            found_speech = False
            for cand in candidates:
                if cand in selected:
                    continue
                if cand["start"] >= r_start and cand["end"] <= r_end:
                    overlaps = any(cand["start"] < item["end"] - 5 and cand["end"] > item["start"] + 5 for item in selected)
                    if not overlaps:
                        selected.append(cand)
                        found_speech = True
                        break

            if found_speech:
                continue

            # 2. Try to form a speech candidate from words within this uncovered range
            range_words = [w for w in words if float(w.get("start", 0)) >= r_start and float(w.get("end", 0)) <= r_end]
            if len(range_words) >= 4:
                s_start = float(range_words[0]["start"])
                s_end = min(r_end, s_start + clip_dur)
                sub_words = [w for w in range_words if float(w.get("start", 0)) >= s_start and float(w.get("end", 0)) <= s_end]
                text = " ".join(str(w.get("word", "")).strip() for w in sub_words).strip()
                if len(text.split()) >= 4:
                    c_dur = round(max(5.0, s_end - s_start), 1)
                    selected.append({
                        "start": round(s_start, 2),
                        "end": round(s_start + c_dur, 2),
                        "duration": c_dur,
                        "text": text,
                        "score": 52,
                        "category": config["label"],
                        "title": make_title(text, template),
                        "visual_cues": sum(1 for stamp in (scene_changes or []) if s_start < stamp < s_start + c_dur),
                    })
                    continue

            # 3. Create visual/pacing fallback candidate using scene_changes data
            scenes_in_range = [s for s in (scene_changes or []) if r_start <= s <= r_end]
            if scenes_in_range:
                # Find the 3-5 second window with the most scene cuts (highest visual dynamism)
                win_size = min(4.0, max(3.0, range_dur))
                best_t = r_start
                max_cuts = -1
                step = 0.5
                curr_t = r_start
                while curr_t + win_size <= r_end:
                    cuts = sum(1 for s in scenes_in_range if curr_t <= s <= curr_t + win_size)
                    if cuts > max_cuts:
                        max_cuts = cuts
                        best_t = curr_t
                    curr_t += step
                # Center the clip window on this peak dynamism zone
                mid_point = best_t + win_size / 2.0
                c_start = max(r_start, mid_point - clip_dur / 2.0)
                c_end = min(r_end, c_start + clip_dur)
                if c_end == r_end:
                    c_start = max(r_start, c_end - clip_dur)
                final_start = round(c_start, 2)
                final_end = round(c_end, 2)
            else:
                # No scene cuts: use fixed temporal slices of the uncovered range (divide evenly)
                clips_needed = count - len(selected)
                slice_dur = min(clip_dur, range_dur / max(1, clips_needed))
                final_start = round(r_start, 2)
                final_end = round(min(r_end, r_start + max(5.0, slice_dur)), 2)

            fallback_candidate = {
                "start": final_start,
                "end": final_end,
                "duration": round(final_end - final_start, 1),
                "text": "",
                "fallback": True,
                "score": 45,
                "category": config["label"],
                "title": f"{config['label']} Highlight",
                "visual_cues": sum(1 for stamp in (scene_changes or []) if final_start < stamp < final_end),
            }
            selected.append(fallback_candidate)

    selected.sort(key=lambda item: item["start"])
    return selected


def detect_scene_changes(path: Path, job_id: str | None = None) -> list[float]:
    """Use FFmpeg's scene-change detector as a lightweight visual signal."""
    if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
        raise JobCancelledException("Processing was cancelled by user.")
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", "fps=2,scale=320:-2:flags=fast_bilinear,select='gt(scene,0.28)',showinfo", "-an", "-f", "null", "-"]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if job_id:
            with LOCK:
                ACTIVE_PROCESSES[job_id] = process
        try:
            stdout, stderr = process.communicate(timeout=300)
        finally:
            if job_id:
                with LOCK:
                    ACTIVE_PROCESSES.pop(job_id, None)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
        raise JobCancelledException("Processing was cancelled by user.")
    if process.returncode not in (0, 255):
        return []
    return sorted({round(float(match), 2) for match in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", stderr or "")})


def identify_video_style(
    words: list[dict],
    transcript: str,
    scene_changes: list[float],
    video_duration: float,
    title: str = "",
) -> dict:
    """Analyze speech vocabulary, pacing, repetition, and scene velocity to identify the best clip style."""
    text_lower = transcript.lower()
    title_lower = title.lower()
    duration_min = max(0.1, video_duration / 60.0)
    cuts_per_min = len(scene_changes) / duration_min

    scores = {name: 10.0 for name in TEMPLATES}
    reasons_map: dict[str, list[str]] = {name: [] for name in TEMPLATES}

    # 1. Template keywords & hooks density
    for name, data in TEMPLATES.items():
        kw_matches = sum(1 for kw in data.get("keywords", set()) if kw in text_lower)
        hook_matches = sum(2 for hook in data.get("hooks", ()) if hook in text_lower)
        points = (kw_matches * 1.8) + (hook_matches * 3.5)
        scores[name] += points
        if kw_matches + hook_matches >= 3:
            reasons_map[name].append(f"Contains key {name} phrases and terminology")

    # 2. Domain-specific vocabulary signals
    # Music signals
    music_terms = {
        "verse", "chorus", "melody", "rhythm", "lyrics", "beat", "instrumental",
        "guitar", "piano", "vocals", "sing", "singing", "song", "track", "concert",
        "drop", "dj", "rap", "band", "acoustic", "live performance", "feat", "remix"
    }
    music_hits = sum(1 for term in music_terms if term in text_lower)
    if music_hits >= 2:
        scores["music"] += music_hits * 4.0
        reasons_map["music"].append("Musical terminology and performance cues detected")

    # Gaming signals
    gaming_terms = {
        "gameplay", "boss", "respawn", "fps", "loot", "match", "clutch", "gg",
        "controller", "mod", "quest", "speedrun", "minecraft", "fortnite",
        "valorant", "roblox", "apex", "pvp", "rpg", "npc", "damage", "health",
        "kill", "headshot", "level up", "spawn", "inventory", "glitch", "steam"
    }
    gaming_hits = sum(1 for term in gaming_terms if term in text_lower)
    if gaming_hits >= 2:
        scores["gaming"] += gaming_hits * 4.0
        reasons_map["gaming"].append("Gaming vocabulary and gameplay action detected")

    # Educational signals
    edu_terms = {
        "tutorial", "how to", "step 1", "step 2", "for example", "concept",
        "technique", "method", "lesson", "guide", "definition", "science",
        "formula", "analysis", "principles", "understand", "explanation", "in summary"
    }
    edu_hits = sum(1 for term in edu_terms if term in text_lower)
    if edu_hits >= 2:
        scores["educational"] += edu_hits * 4.0
        reasons_map["educational"].append("Instructive phrasing and step-by-step structure")

    # Story signals
    story_terms = {
        "one day", "suddenly", "what happened was", "remember when", "years ago",
        "journey", "turned out", "at the time", "after that", "in the end",
        "my life", "true story", "experience", "we decided to", "the moment i"
    }
    story_hits = sum(1 for term in story_terms if term in text_lower)
    if story_hits >= 2:
        scores["story"] += story_hits * 4.0
        reasons_map["story"].append("Narrative storytelling cues and chronological pacing")

    # Funny signals
    funny_terms = {
        "lol", "lmao", "haha", "hahaha", "hilarious", "joke", "prank",
        "awkward", "fail", "omg", "ridiculous", "crazy", "bloopers", "meme"
    }
    funny_hits = sum(1 for term in funny_terms if term in text_lower)
    exclamation_count = transcript.count("!")
    if funny_hits >= 2 or exclamation_count >= 5:
        scores["funny"] += (funny_hits * 3.5) + min(12.0, exclamation_count * 0.8)
        reasons_map["funny"].append("High comedic reaction markers and expressive dialogue")

    # Podcast signals
    podcast_terms = {
        "welcome back", "our guest", "guest today", "podcast", "episode",
        "interview", "let me ask", "what do you think", "perspective",
        "honestly", "in my opinion", "agree with that", "fascinating", "thanks for coming"
    }
    podcast_hits = sum(1 for term in podcast_terms if term in text_lower)
    if podcast_hits >= 2:
        scores["podcast"] += podcast_hits * 4.0
        reasons_map["podcast"].append("Conversational interview dialogue and host cues")

    # 3. Lyrical chorus / refrain repetition (strongest unique musical signal)
    phrases = [w.get("word", "").lower().strip(".,!?;:\"'") for w in words if w.get("word", "").strip()]
    if len(phrases) >= 12:
        ngrams: dict[tuple[str, ...], int] = {}
        for i in range(len(phrases) - 3):
            gram = tuple(phrases[i:i+4])
            if all(len(p) > 2 for p in gram):
                ngrams[gram] = ngrams.get(gram, 0) + 1
        repeated_phrases = sum(1 for count in ngrams.values() if count >= 2)
        if repeated_phrases >= 2:
            scores["music"] += repeated_phrases * 6.0
            reasons_map["music"].append(f"Identified {repeated_phrases} repeated lyrical choruses or refrains")

    # 4. Visual cut pacing
    if cuts_per_min >= 16.0:
        scores["gaming"] += 8.0
        scores["music"] += 6.0
        scores["funny"] += 4.0
        reasons_map["gaming"].append("High-velocity scene changes characteristic of gaming")
    elif cuts_per_min <= 6.0:
        scores["podcast"] += 7.0
        scores["educational"] += 5.0
        reasons_map["podcast"].append("Steady visual pacing characteristic of interview discussions")

    # 5. Title hints
    if title_lower:
        for name, data in TEMPLATES.items():
            if name in title_lower or any(kw in title_lower for kw in data.get("keywords", ())):
                scores[name] += 15.0
                reasons_map[name].append(f"Video title mentions '{name}' keywords")

    ranked_styles = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_style, top_score = ranked_styles[0]
    runner_up_style, second_score = ranked_styles[1]

    margin = (top_score - second_score) / max(1.0, top_score)
    confidence = round(min(0.98, max(0.55, 0.55 + margin * 0.45)), 2)

    best_reasons = reasons_map[best_style]
    if not best_reasons:
        best_reasons = ["Best overall fit based on speech patterns and structure"]

    return {
        "best_style": best_style,
        "best_label": TEMPLATES[best_style]["label"],
        "confidence": confidence,
        "scores": {k: round(v, 1) for k, v in scores.items()},
        "reasons": best_reasons[:3],
    }


def apply_prompt_edit_plan(candidates: list[dict], transcript: str, prompt: str, template: str) -> tuple[list[dict], str | None]:
    """Optionally rerank candidate moments using an OpenAI-compatible chat completion API."""
    if not prompt.strip():
        return candidates, None
    if not AI_BASE_URL or not AI_API_KEY:
        return candidates, "Your editing brief was saved, but AI reranking is not configured. Set AI_BASE_URL and AI_API_KEY to enable it."
    payload = {
        "model": AI_MODEL,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a short-form video editor. Select only from supplied candidate clips. Return JSON with a 'ranked' array of objects containing 'index' (zero-based candidate index), 'title' (short, accurate title), 'reason' (one concise sentence), and 'score' (integer 1-100). Never invent quotes or timestamps. Respect the user's editing brief and chosen template. For music, prioritize catchy hooks, choruses, drops, and musical performances."},
            {"role": "user", "content": json.dumps({"template": template, "editing_brief": prompt[:1200], "transcript_context": transcript[:10000], "candidates": [{"index": i, "start": c["start"], "end": c["end"], "score": c["score"], "text": c["text"][:900]} for i, c in enumerate(candidates[:40])]}, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        f"{AI_BASE_URL}/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        ranked = []
        seen = set()
        for item in parsed.get("ranked", []):
            index = int(item.get("index", -1))
            if index < 0 or index >= min(40, len(candidates)) or index in seen:
                continue
            seen.add(index)
            candidate = dict(candidates[index])
            candidate["score"] = max(1, min(100, int(item.get("score", candidate["score"]))))
            candidate["title"] = str(item.get("title") or candidate["title"])[:88]
            candidate["reason"] = str(item.get("reason") or "Selected to match your editing brief.")[:300]
            ranked.append(candidate)
        if not ranked:
            return candidates, "The AI response did not contain valid clip selections, so Cutflow kept its automatic ranking."
        ranked.sort(key=lambda item: item["score"], reverse=True)
        selected = []
        for candidate in ranked:
            if not any(candidate["start"] < old["end"] - 5 and candidate["end"] > old["start"] + 5 for old in selected):
                selected.append(candidate)
        return selected, None
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, IndexError) as exc:
        return candidates, f"AI reranking was unavailable, so Cutflow kept its automatic ranking ({str(exc)[:180]})."


def make_title(text: str, template: str) -> str:
    cleaned = re.sub(r"\s+", " ", re.sub(r"[^\w\s'’-]", "", text)).strip()
    words = cleaned.split()
    title = " ".join(words[:9])
    if len(words) > 9:
        title += "…"
    return title[:88] or TEMPLATES[template]["label"]


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole = int(seconds % 60)
    centiseconds = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{whole:02d}.{centiseconds:02d}"


def _caption_groups(visible: list[dict], max_chars: int, max_words: int = 3) -> list[list[dict]]:
    """Create short, high-retention phrase captions matching Captions.ai 2-4 word layout."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    for word in visible:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        gap = float(word["start"]) - float(current[-1]["end"]) if current else 0.0
        proposed = " ".join([str(item["word"]).strip() for item in current] + [token])
        punctuation_break = bool(current and re.search(r"[.!?,;:][\"'’)]?$", str(current[-1]["word"])))
        if current and (len(current) >= max_words or len(proposed) > max_chars or gap > 0.65 or punctuation_break):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def _ass_escape(text: str) -> str:
    # User speech is untrusted caption text; prevent it from injecting ASS override tags.
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace(",", r"\,")


def extract_headline(candidate: list[dict] | str, template: str = "podcast") -> str:
    """Extract a punchy 2-4 word hook headline for the top third of the video (Zone 1)."""
    if isinstance(candidate, list):
        raw_text = " ".join(str(w.get("word", "")).strip() for w in candidate[:12])
    else:
        raw_text = str(candidate)
    cleaned = re.sub(r"[^\w\s'’-]", " ", raw_text).strip()
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        label = TEMPLATES.get(template, {}).get("label", "KEY MOMENT")
        return label.split()[0].upper()

    lower = " ".join(tokens).lower()
    hook_patterns = [
        r"^(the (?:biggest|greatest) mistake)",
        r"^(the truth (?:is|about) \w+ \w+)",
        r"^(the truth (?:is|about) \w+)",
        r"^(here'?s why \w+ \w+)",
        r"^(here'?s why \w+)",
        r"^(how to \w+ \w+)",
        r"^(what people don'?t)",
        r"^(i never expected)",
        r"^(the secret to \w+)",
        r"^(stop doing this)",
        r"^(rule (?:number|#) \d+)",
        r"^(drop the beat)",
    ]
    for pattern in hook_patterns:
        match = re.match(pattern, lower)
        if match:
            matched_words = match.group(1).split()
            headline = " ".join(matched_words[:4]).upper()
            return headline[:24].rstrip()

    chosen = tokens[:min(4, max(2, len(tokens)))]
    headline = " ".join(chosen).upper()
    return headline[:24].rstrip()


def parse_caption_prompt(prompt: str, candidate_text: str = "") -> dict:
    """Translate natural language creator prompts into exact ASS layout and styling tokens."""
    prompt_lower = (prompt or "").lower().strip()
    if not prompt_lower:
        return dict(CAPTION_STYLES.get("focus", CAPTION_STYLES["clean"]))

    # Determine base style
    if any(k in prompt_lower for k in ("linen", "editorial", "serif")):
        base_key = "linen"
    elif any(k in prompt_lower for k in ("evo", "frosted", "cyan")):
        base_key = "evo"
    elif any(k in prompt_lower for k in ("lift", "emerald", "banner")):
        base_key = "lift"
    elif any(k in prompt_lower for k in ("stack", "brutalist", "mono", "code", "technical")):
        base_key = "stack"
    elif any(k in prompt_lower for k in ("align", "polaroid", "letterbox")):
        base_key = "align"
    elif any(k in prompt_lower for k in ("impact", "punch", "heavy")):
        base_key = "impact"
    elif any(k in prompt_lower for k in ("hormozi", "gold")):
        base_key = "hormozi"
    elif any(k in prompt_lower for k in ("pop", "bouncy")):
        base_key = "pop"
    elif any(k in prompt_lower for k in ("y2k", "neon")):
        base_key = "y2k"
    elif any(k in prompt_lower for k in ("focus", "badge", "box", "inverted")):
        base_key = "focus"
    else:
        base_key = "focus"

    style = dict(CAPTION_STYLES.get(base_key, CAPTION_STYLES["focus"]))

    # Font customization
    if any(k in prompt_lower for k in ("serif", "editorial", "georgia")):
        style["font"] = "Merriweather"
    elif any(k in prompt_lower for k in ("mono", "code", "technical", "terminal")):
        style["font"] = "JetBrainsMono"
    elif "sans" in prompt_lower:
        style["font"] = "Montserrat" 

    # Accent color override (&H00BBGGRR)
    if "yellow" in prompt_lower or "gold" in prompt_lower:
        style["accent_color"] = "&H0000FFFF"
    elif "cyan" in prompt_lower or "blue" in prompt_lower:
        style["accent_color"] = "&H00FFFF00"
    elif "green" in prompt_lower or "emerald" in prompt_lower or "lime" in prompt_lower:
        style["accent_color"] = "&H005FFFD5"
    elif "pink" in prompt_lower or "magenta" in prompt_lower or "purple" in prompt_lower:
        style["accent_color"] = "&H00FF00FF"
    elif "red" in prompt_lower or "crimson" in prompt_lower:
        style["accent_color"] = "&H000000FF"
    elif "white" in prompt_lower:
        style["accent_color"] = "&H00FFFFFF"

    # Layout tokens
    if any(k in prompt_lower for k in ("badge", "box", "inverted", "focus")):
        style["badge_box"] = True
    if any(k in prompt_lower for k in ("pill", "card", "rounded")):
        style["pill"] = True
    if any(k in prompt_lower for k in ("caps", "uppercase", "all caps")):
        style["uppercase"] = True
    if any(k in prompt_lower for k in ("pop", "kinetic", "bounce")):
        style["kinetic_pop"] = True
    if any(k in prompt_lower for k in ("banner", "header")):
        style["top_banner"] = True
    if any(k in prompt_lower for k in ("polaroid", "letterbox", "frame")):
        style["letterbox"] = True
    if any(k in prompt_lower for k in ("side", "vertical", "stack", "crosshair")):
        style["vertical_side"] = True

    # Headline control
    style["show_headline"] = "no headline" not in prompt_lower and "no hook" not in prompt_lower

    return style


def resolve_caption_spec(
    caption_style: str | CaptionSpec | dict = "clean",
    custom_style: dict | CaptionSpec | None = None,
    uppercase: bool = False,
    kinetic_pop: bool = True,
) -> CaptionSpec:
    if isinstance(caption_style, CaptionSpec):
        spec = caption_style
    elif isinstance(caption_style, dict):
        spec = CAPTION_PRESETS.get("clean") or CAPTION_PRESETS.get("focus") or next(iter(CAPTION_PRESETS.values()))
        custom_style = caption_style
    else:
        key = str(caption_style or "clean")
        spec = CAPTION_PRESETS.get(key) or CAPTION_PRESETS.get("clean") or CAPTION_PRESETS.get("focus") or next(iter(CAPTION_PRESETS.values()))

    if custom_style:
        if isinstance(custom_style, CaptionSpec):
            spec = custom_style
        elif isinstance(custom_style, dict):
            overrides: dict = {}
            if custom_style.get("font"):
                raw_font = str(custom_style["font"])
                if any(k in raw_font.lower() for k in ("merriweather", "serif", "georgia")):
                    overrides["font"] = "Merriweather"
                elif any(k in raw_font.lower() for k in ("mono", "code", "technical", "terminal", "jetbrains")):
                    overrides["font"] = "JetBrains Mono"
                else:
                    overrides["font"] = "Montserrat"
            if custom_style.get("headline_font"):
                overrides["headline_font"] = custom_style["headline_font"]
            if custom_style.get("base_color"):
                overrides["primary"] = custom_style["base_color"]
            if custom_style.get("accent_color"):
                overrides["accent"] = custom_style["accent_color"]
            if custom_style.get("outline_color"):
                overrides["outline"] = custom_style["outline_color"]
            if custom_style.get("upcoming_color"):
                overrides["upcoming"] = custom_style["upcoming_color"]
            if custom_style.get("back_color"):
                overrides["fill"] = custom_style["back_color"]
            if custom_style.get("primary"):
                overrides["primary"] = custom_style["primary"]
            if custom_style.get("accent"):
                overrides["accent"] = custom_style["accent"]
            if custom_style.get("outline"):
                overrides["outline"] = custom_style["outline"]
            if custom_style.get("upcoming"):
                overrides["upcoming"] = custom_style["upcoming"]
            if custom_style.get("fill"):
                overrides["fill"] = custom_style["fill"]
            if custom_style.get("badge_box"):
                overrides["caption_box"] = "per_word"
                overrides["active"] = "box"
            if custom_style.get("pill"):
                overrides["caption_box"] = "pill"
            if custom_style.get("letterbox"):
                overrides["frame"] = "letterbox"
            if custom_style.get("vertical_side"):
                overrides["rail"] = "CUTFLOW // MOTION GRAPHICS"
            if custom_style.get("top_banner"):
                overrides["headline"] = "banner"
            if custom_style.get("show_headline") is False:
                overrides["headline"] = "none"
            if custom_style.get("glow") is not None:
                try:
                    overrides["glow"] = float(custom_style["glow"])
                except (ValueError, TypeError):
                    pass
            if custom_style.get("shadow") is not None:
                try:
                    overrides["shadow"] = float(custom_style["shadow"])
                except (ValueError, TypeError):
                    pass
            if custom_style.get("outline_width") is not None:
                try:
                    overrides["outline_width"] = float(custom_style["outline_width"])
                except (ValueError, TypeError):
                    pass
            if "uppercase" in custom_style and custom_style["uppercase"] is not None:
                overrides["uppercase"] = bool(custom_style["uppercase"])
            if "kinetic_pop" in custom_style and custom_style["kinetic_pop"] is not None:
                overrides["active_pop"] = bool(custom_style["kinetic_pop"])
            if overrides:
                spec = spec.with_overrides(**overrides)

    if uppercase:
        spec = spec.with_overrides(uppercase=True)
    if not kinetic_pop:
        spec = spec.with_overrides(active_pop=False)

    return spec


def write_ass(
    path: Path,
    words: list[dict],
    start: float,
    end: float,
    aspect: str,
    caption_style: str = "clean",
    auto_emoji: bool = True,
    uppercase: bool = False,
    kinetic_pop: bool = True,
    custom_style: dict | None = None,
    auto_headline: bool = True,
    candidate_text: str = "",
    template: str = "podcast",
) -> None:
    spec = resolve_caption_spec(
        caption_style,
        custom_style=custom_style,
        uppercase=uppercase,
        kinetic_pop=kinetic_pop,
    )
    ass_content = ass_engine.compile_ass(
        spec,
        words=words,
        start=start,
        end=end,
        aspect=aspect,
        auto_emoji=auto_emoji,
        emoji_map=EMOJI_MAP,
        auto_headline=auto_headline,
        candidate_text=candidate_text,
        template=template,
        extract_headline=extract_headline,
    )
    path.write_text(ass_content, encoding="utf-8")


def write_srt(path: Path, words: list[dict], start: float, end: float, auto_emoji: bool = True, uppercase: bool = False) -> None:
    visible = [w for w in words if float(w["end"]) > start and float(w["start"]) < end]
    groups = _caption_groups(visible, max_chars=34)
    lines = []
    idx = 1
    for group in groups:
        line_start = max(0.0, float(group[0]["start"]) - start)
        line_end = min(end - start, float(group[-1]["end"]) - start + 0.14)
        if line_end <= line_start:
            continue
        tokens = []
        for w in group:
            raw_w = str(w.get("word", "")).strip()
            norm = raw_w.lower().strip(".,!?;:\"'")
            token = raw_w
            if auto_emoji and norm in EMOJI_MAP:
                token = f"{token} {EMOJI_MAP[norm]}"
            if uppercase:
                token = token.upper()
            tokens.append(token)
        text = " ".join(tokens)
        s_h, s_m, s_s = int(line_start // 3600), int((line_start % 3600) // 60), line_start % 60
        e_h, e_m, e_s = int(line_end // 3600), int((line_end % 3600) // 60), line_end % 60
        start_str = f"{s_h:02d}:{s_m:02d}:{int(s_s):02d},{int((s_s % 1) * 1000):03d}"
        end_str = f"{e_h:02d}:{e_m:02d}:{int(e_s):02d},{int((e_s % 1) * 1000):03d}"
        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
        idx += 1
    path.write_text("\n".join(lines) if lines else "1\n00:00:00,000 --> 00:00:01,000\n...\n", encoding="utf-8")


def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str, caption_style: str = "clean", template: str = "podcast", job_id: str | None = None, fit_mode: str = "blur") -> None:
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    width, height = dimensions[aspect]
    ass_path = subtitle_path.resolve().as_posix().replace(":", r"\:")
    fonts_dir = FONTS_DIR.resolve().as_posix().replace(":", r"\:")
    ass_filter = f"ass='{ass_path}':fontsdir='{fonts_dir}'"
    profile = STYLE_PROFILES.get(template, STYLE_PROFILES["podcast"])
    eq_filter = profile.get("eq", "contrast=1.04:saturation=1.06:brightness=0.005")
    unsharp_filter = profile.get("unsharp", "5:5:0.25:3:3:0.0")

    # Detect source dimensions to determine if smart canvas fill is needed
    try:
        source_info = probe_video(source)
        s_w = source_info.get("width") or 1920
        s_h = source_info.get("height") or 1080
    except Exception:
        s_w, s_h = 1920, 1080

    source_ratio = s_w / s_h
    target_ratio = width / height
    is_mismatch = abs(source_ratio - target_ratio) > 0.18

    # Canvas Framing & Background Mode:
    # 1. letterbox: clean cinematic black bars (100% video visible, zero blur, zero zoom)
    # 2. crop: smart punch-in fill (fills canvas completely, no bars, no blur)
    # 3. blur: ambient softened background (keeps 100% video visible with blur fill)
    use_filter_complex = False
    if is_mismatch and fit_mode == "letterbox":
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"eq={eq_filter},unsharp={unsharp_filter},{ass_filter}"
        )
    elif is_mismatch and fit_mode == "crop":
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},eq={eq_filter},unsharp={unsharp_filter},{ass_filter}"
        )
    elif is_mismatch and aspect in {"9:16", "1:1"} and fit_mode != "crop":
        blur_radius = "28:5" if aspect == "9:16" else "24:4"
        dim_amount = "-0.12" if aspect == "9:16" else "-0.10"
        filter_graph = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur_radius},eq=brightness={dim_amount}:contrast=1.06[bg];"
            f"[0:v]scale={width}:-2:flags=lanczos,eq={eq_filter},unsharp={unsharp_filter}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[comp];"
            f"[comp]{ass_filter}[vout]"
        )
        use_filter_complex = True
    else:
        filter_graph = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},eq={eq_filter},unsharp={unsharp_filter},{ass_filter}"

    duration = max(1, end - start)
    if use_filter_complex:
        # Complex filtergraph: two [0:v] split paths merged via overlay
        # Must use -filter_complex + explicit -map to avoid 'multiple inputs' error
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
            "-filter_complex", filter_graph,
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", os.getenv("FFMPEG_PRESET", "veryfast"),
            "-crf", "21", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(output),
        ]
    else:
        # Simple filtergraph: single input, single output chain — -vf is correct
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
            "-vf", filter_graph,
            "-c:v", "libx264", "-preset", os.getenv("FFMPEG_PRESET", "veryfast"),
            "-crf", "21", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(output),
        ]
    run_command(command, timeout=1200, job_id=job_id)


def render_clip_headless(
    source: Path,
    output: Path,
    timeline_path: Path,
    start: float,
    end: float,
    aspect: str,
    job_id: str | None = None,
    fit_mode: str = "blur",
) -> bool:
    """Render a video clip using the deterministic Node/Skia headless canvas engine.

    Guarantees strict 1:1 pixel parity with the frontend WYSIWYG canvas preview.
    Falls back gracefully to FFmpeg libass if Node/@napi-rs/canvas is unavailable.
    """
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    width, height = dimensions.get(aspect, (1080, 1920))
    duration = max(1.0, end - start)
    headless_script = Path(__file__).resolve().parent / "render_headless.js"

    node_bin = shutil.which("node")
    if not node_bin or not headless_script.is_file():
        return False

    cmd = [
        node_bin,
        str(headless_script),
        "--timeline", str(timeline_path),
        "--source", str(source),
        "--output", str(output),
        "--start", f"{start:.3f}",
        "--duration", f"{duration:.3f}",
        "--width", str(width),
        "--height", str(height),
        "--fps", "30",
        "--fit-mode", fit_mode,
        "--preset", os.getenv("FFMPEG_PRESET", "veryfast"),
        "--crf", "21",
    ]

    try:
        run_command(cmd, timeout=1200, job_id=job_id)
        return output.is_file() and output.stat().st_size > 0
    except Exception as exc:
        print(f"[render_clip_headless] Fallback to libass: {exc}")
        return False



def export_dimensions(aspect: str, resolution: str) -> tuple[int, int]:
    """Return consistent, even output dimensions for the requested quality tier."""
    dimensions = {
        "9:16": {"480": (480, 854), "720": (720, 1280), "1080": (1080, 1920), "2k": (1440, 2560)},
        "1:1": {"480": (480, 480), "720": (720, 720), "1080": (1080, 1080), "2k": (1440, 1440)},
        "16:9": {"480": (854, 480), "720": (1280, 720), "1080": (1920, 1080), "2k": (2560, 1440)},
    }
    if resolution.lower() not in EXPORT_RESOLUTIONS:
        raise HTTPException(400, "Choose 480p, 720p, 1080p, or 2K.")
    if aspect not in dimensions:
        raise HTTPException(400, "This project has an unsupported aspect ratio.")
    return dimensions[aspect][resolution.lower()]


def render_export(source: Path, output: Path, aspect: str, resolution: str) -> None:
    """Create a cached quality variant from the already-captioned master clip."""
    width, height = export_dimensions(aspect, resolution)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vf", f"scale={width}:{height}:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", os.getenv("EXPORT_FFMPEG_PRESET", "veryfast"),
        "-crf", "21" if resolution.lower() in {"1080", "2k"} else "23",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output),
    ]
    run_command(command, timeout=1200)


def process_job(job_id: str) -> None:
    job = JOBS.get(job_id)
    if not job or job_id in CANCELLED_JOBS or job.get("status") == "cancelled":
        return

    def check_cancelled():
        if job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled":
            raise JobCancelledException("Processing was cancelled by user.")

    source: Path | None = None
    try:
        check_cancelled()
        update_job(job_id, status="processing", progress=4, stage="Preparing video", message="Checking the source video.")
        if job.get("source_url"):
            source = download_source(job["source_url"], job_id)
        else:
            source = Path(job["source_path"])
        if not source.exists():
            raise RuntimeError("The source video could not be found.")
        check_cancelled()
        metadata = probe_video(source)
        check_cancelled()
        update_job(job_id, progress=9, stage="Analyzing audio", message=f"Video is {metadata['duration'] / 60:.1f} minutes long.", video=metadata)
        words, transcript, language = transcribe(source, job_id)
        check_cancelled()
        update_job(job_id, progress=28, stage="Analyzing visuals", message="Detecting scene changes to help find stronger moments.", transcript_preview=transcript[:1200], language=language)
        scene_changes = detect_scene_changes(source, job_id=job_id)
        check_cancelled()
        update_job(job_id, progress=34, stage="Finding highlights", message=f"Ranking moments with speech and {len(scene_changes)} detected scene changes.", transcript_preview=transcript[:1200], language=language, scene_change_count=len(scene_changes))

        # Automatic Content Style Identification & Matching
        style_info = identify_video_style(words, transcript, scene_changes, metadata["duration"], title=source.stem)
        detected_style = style_info["best_style"]
        detected_label = TEMPLATES[detected_style]["label"]
        selected_style = job["template"]
        selected_label = job["template_label"]

        # Automatically adopt the detected style ONLY if user chose "auto"
        if selected_style == "auto":
            job["template"] = detected_style
            job["template_label"] = detected_label
            style_match = {
                "matched": True,
                "auto_detected": True,
                "detected_style": detected_style,
                "detected_label": detected_label,
                "original_style": selected_style,
                "confidence": style_info["confidence"],
                "reasons": style_info["reasons"],
                "scores": style_info["scores"],
                "message": f"Auto-detected {detected_label} ({int(style_info['confidence'] * 100)}% match) · Tailored {detected_label} finishing automatically applied.",
            }
        else:
            is_match = (selected_style == detected_style)
            style_match = {
                "matched": is_match,
                "auto_detected": False,
                "detected_style": detected_style,
                "detected_label": detected_label,
                "confidence": style_info["confidence"],
                "reasons": style_info["reasons"],
                "scores": style_info["scores"],
                "message": (
                    f"Content verified as {detected_label} ({int(style_info['confidence'] * 100)}% match) · Tailored {detected_label} finishing applied."
                    if is_match
                    else f"Content identified as {detected_label} · Applying chosen {selected_label} style."
                ),
            }

        update_job(
            job_id,
            style_match=style_match,
            template=job["template"],
            template_label=job["template_label"],
            detected_style=detected_style,
            detected_label=detected_label,
        )

        check_cancelled()
        candidate_limit = max(job["clip_count"] * 5, job["clip_count"]) if job.get("edit_prompt", "").strip() else job["clip_count"]
        candidates = rank_candidates(words, job["template"], job["min_duration"], job["max_duration"], metadata["duration"], candidate_limit, scene_changes)
        candidates, ai_warning = apply_prompt_edit_plan(candidates, transcript, job.get("edit_prompt", ""), job["template"])
        if ai_warning:
            update_job(job_id, warning=ai_warning)
        elif job["template"] == "music":
            has_musical_signals = any(
                c.get("score", 0) >= 50 or any(kw in c.get("text", "").lower() for kw in ("chorus", "verse", "drop", "beat", "melody", "song", "sing", "music", "dance", "rhythm", "vibe", "track", "yeah", "baby", "love", "night"))
                for c in candidates
            )
            if not has_musical_signals and not style_match.get("warning"):
                update_job(job_id, warning="This video appears to contain spoken dialogue rather than musical performance. For best results with speech, try the 'Podcast' or 'Educational' style.")
        candidates = candidates[:job["clip_count"]]
        if not candidates:
            raise RuntimeError("No usable moments were found. Try a longer video with clear speech or adjust the duration range.")

        caption_style_to_use = job.get("caption_style", "focus")
        caption_mode = job.get("caption_mode", "auto")
        caption_prompt = job.get("caption_prompt", "")
        auto_headline = job.get("auto_headline", True)
        auto_emoji = job.get("auto_emoji", False)
        uppercase = job.get("uppercase", False)

        enriched_candidates = []
        for index, candidate in enumerate(candidates, start=1):
            custom_style = None
            if caption_mode == "prompt" and caption_prompt:
                custom_style = parse_caption_prompt(caption_prompt, candidate.get("text", ""))
            spec = resolve_caption_spec(
                caption_style_to_use,
                custom_style=custom_style,
                uppercase=uppercase,
                kinetic_pop=job.get("kinetic_pop", True),
            )
            is_fallback = bool(candidate.get("fallback"))
            cand_words = [] if is_fallback else words
            cand_title = candidate.get("title", "") if is_fallback else extract_headline(candidate.get("text", ""), job["template"])
            timeline_data = build_kinetic_timeline(
                cand_words,
                candidate["start"],
                candidate["end"],
                spec,
                aspect=job["aspect_ratio"],
                headline_text=cand_title if auto_headline else None,
                emoji_map=EMOJI_MAP if auto_emoji else None,
                clip_id=f"cutflow-{index:02d}",
            )
            enriched_candidates.append({
                **candidate,
                "clip_index": index,
                "words": timeline_data["words"],
                "timeline": timeline_data,
            })
        candidates = enriched_candidates
        update_job(job_id, candidates=candidates)

        output_dir = OUTPUTS / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        completed = []
        profile = STYLE_PROFILES.get(job["template"], STYLE_PROFILES["podcast"])
        fit_mode = job.get("fit_mode", "blur")
        for index, candidate in enumerate(candidates, start=1):
            check_cancelled()
            update_job(job_id, progress=35 + int((index - 1) / len(candidates) * 60), stage=f"Rendering clip {index} of {len(candidates)}", message=f"Creating {job['aspect_ratio']} video with {profile['label']} finishing.")
            clip_name = f"cutflow-{index:02d}.mp4"
            output = output_dir / clip_name
            ass_path = output_dir / f"cutflow-{index:02d}.ass"
            srt_path = output_dir / f"cutflow-{index:02d}.srt"
            caption_style_to_use = job.get("caption_style", "focus")
            caption_mode = job.get("caption_mode", "auto")
            caption_prompt = job.get("caption_prompt", "")
            auto_headline = job.get("auto_headline", True)
            custom_style = None
            if caption_mode == "prompt" and caption_prompt:
                custom_style = parse_caption_prompt(caption_prompt, candidate.get("text", ""))
            auto_emoji = job.get("auto_emoji", False)
            uppercase = job.get("uppercase", False)

            # Fallback candidates have no words: render Zone 1 topic card only (no dialogue subtitles)
            is_fallback = bool(candidate.get("fallback"))
            words_for_ass = [] if is_fallback else words
            candidate_text_for_ass = candidate.get("title", "") if is_fallback else candidate.get("text", "")
            auto_headline_for_ass = True if is_fallback else auto_headline

            spec = resolve_caption_spec(
                caption_style_to_use,
                custom_style=custom_style,
                uppercase=uppercase,
                kinetic_pop=job.get("kinetic_pop", True),
            )
            ass_content = ass_engine.compile_ass(
                spec,
                words=words_for_ass,
                start=candidate["start"],
                end=candidate["end"],
                aspect=job["aspect_ratio"],
                auto_emoji=auto_emoji,
                emoji_map=EMOJI_MAP,
                auto_headline=auto_headline_for_ass,
                candidate_text=candidate_text_for_ass,
                template=job["template"],
                extract_headline=extract_headline,
            )
            ass_path.write_text(ass_content, encoding="utf-8")
            write_srt(srt_path, words_for_ass, candidate["start"], candidate["end"], auto_emoji=auto_emoji, uppercase=uppercase)
            check_cancelled()

            # Save timeline JSON alongside ASS and SRT
            timeline_path = output_dir / f"cutflow-{index:02d}.json"
            timeline_path.write_text(json.dumps(candidate.get("timeline", {}), indent=2), encoding="utf-8")

            # Deterministic headless Skia export with 1:1 preview parity, fallback to libass
            rendered_ok = render_clip_headless(
                source, output, timeline_path,
                candidate["start"], candidate["end"],
                job["aspect_ratio"], job_id=job_id, fit_mode=fit_mode,
            )
            if not rendered_ok:
                render_clip(source, output, ass_path, candidate["start"], candidate["end"], job["aspect_ratio"], caption_style_to_use, template=job["template"], job_id=job_id, fit_mode=fit_mode)
            completed.append({
                **candidate,
                "id": str(uuid.uuid4()),
                "filename": clip_name,
                "download_url": f"/api/jobs/{job_id}/clips/{clip_name}",
                "srt_url": f"/api/jobs/{job_id}/clips/{clip_name.replace('.mp4', '.srt')}",
                "ass_url": f"/api/jobs/{job_id}/clips/{clip_name.replace('.mp4', '.ass')}",
                "timeline_url": f"/api/jobs/{job_id}/clips/{clip_name}/timeline",
                "size": output.stat().st_size,
                "aspect_ratio": job["aspect_ratio"],
                "finishing_label": profile["label"],
                "finishing_desc": profile["description"],
                "clip_style": job["template"],
            })
            update_job(job_id, clips=completed, progress=35 + int(index / len(candidates) * 60))
        check_cancelled()
        update_job(job_id, status="completed", progress=100, stage="Ready to download", message=f"Created {len(completed)} clips.", clips=completed, transcript_preview=transcript[:1200], language=language)
    except JobCancelledException:
        update_job(job_id, status="cancelled", progress=100, stage="Cancelled", message="Processing was cancelled by user.")
    except Exception as exc:
        if job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled":
            update_job(job_id, status="cancelled", progress=100, stage="Cancelled", message="Processing was cancelled by user.")
        else:
            update_job(job_id, status="failed", progress=100, stage="Needs attention", error=str(exc)[:1500], message="Processing failed. Review the error and try again.")
    finally:
        CANCELLED_JOBS.discard(job_id)
        with LOCK:
            ACTIVE_PROCESSES.pop(job_id, None)


def create_job(
    template: str,
    aspect_ratio: str,
    clip_count: int,
    min_duration: int,
    max_duration: int,
    source_path: str | None = None,
    source_url: str | None = None,
    edit_prompt: str = "",
    caption_style: str = "focus",
    caption_mode: str = "auto",
    caption_prompt: str = "",
    auto_headline: bool = True,
    auto_emoji: bool = False,
    uppercase: bool = False,
    kinetic_pop: bool = True,
    fit_mode: str = "blur",
    job_id: str | None = None,
) -> dict:
    if template not in TEMPLATES and template != "auto":
        raise HTTPException(400, "Choose a valid template.")
    if aspect_ratio not in {"9:16", "1:1", "16:9"}:
        raise HTTPException(400, "Choose a valid aspect ratio.")
    if caption_mode == "auto" and caption_style not in CAPTION_STYLES:
        raise HTTPException(400, "Choose a valid caption style.")
    if fit_mode not in {"blur", "letterbox", "crop"}:
        fit_mode = "blur"
    if not 1 <= clip_count <= 8:
        raise HTTPException(400, "Choose between 1 and 8 clips.")
    if not (10 <= min_duration < max_duration <= 90):
        raise HTTPException(400, "Clip duration must be between 10 and 90 seconds, with minimum below maximum.")
    job_id = job_id or uuid.uuid4().hex
    template_label = "Smart Auto-Detect" if template == "auto" else TEMPLATES[template]["label"]
    job = {
        "id": job_id, "status": "queued", "progress": 0, "stage": "Waiting in queue",
        "message": "Your video is queued for analysis.", "template": template,
        "template_label": template_label, "aspect_ratio": aspect_ratio,
        "clip_count": clip_count, "min_duration": min_duration, "max_duration": max_duration,
        "caption_style": caption_style, "caption_mode": caption_mode,
        "caption_prompt": caption_prompt.strip()[:400], "auto_headline": bool(auto_headline),
        "auto_emoji": bool(auto_emoji), "uppercase": bool(uppercase),
        "kinetic_pop": bool(kinetic_pop), "fit_mode": fit_mode,
        "edit_prompt": edit_prompt.strip()[:1200], "source_path": source_path, "source_url": source_url, "clips": [],
        "created_at": time.time(), "updated_at": time.time(),
    }
    with LOCK:
        active_jobs = sum(1 for existing in JOBS.values() if existing.get("status") in {"queued", "processing"})
        if active_jobs >= MAX_ACTIVE_JOBS:
            raise HTTPException(429, f"Cutflow is busy. Wait for a project to finish before starting another (limit: {MAX_ACTIVE_JOBS} active jobs).")
        JOBS[job_id] = job
        persist_job(job)
    POOL.submit(process_job, job_id)
    return public_job(job)


def public_job(job: dict) -> dict:
    hidden = {"source_path"}
    return {key: value for key, value in job.items() if key not in hidden}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "cutflow", "version": "0.2.0"}


@app.get("/api/templates")
def templates():
    return [{"id": key, "label": value["label"], "description": value["description"]} for key, value in TEMPLATES.items()]


@app.get("/api/caption-styles")
def caption_styles():
    return [{"id": key, "label": value["label"]} for key, value in CAPTION_STYLES.items()]


@app.post("/api/jobs/upload")
async def upload_job(
    file: UploadFile = File(...),
    template: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_count: int = Form(3),
    min_duration: int = Form(20),
    max_duration: int = Form(45),
    edit_prompt: str = Form(""),
    caption_style: str = Form("focus"),
    caption_mode: str = Form("auto"),
    caption_prompt: str = Form(""),
    auto_headline: bool = Form(True),
    auto_emoji: bool = Form(False),
    uppercase: bool = Form(False),
    kinetic_pop: bool = Form(True),
    fit_mode: str = Form("blur"),
):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported video format. Use MP4, MOV, MKV, WEBM, M4V, or AVI.")
    job_id = uuid.uuid4().hex
    destination_dir = UPLOADS / job_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"source{extension}"
    size = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(413, f"Video exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
                output.write(chunk)
    finally:
        await file.close()
    try:
        job = create_job(
            template, aspect_ratio, clip_count, min_duration, max_duration,
            source_path=str(destination), edit_prompt=edit_prompt,
            caption_style=caption_style, caption_mode=caption_mode,
            caption_prompt=caption_prompt, auto_headline=auto_headline,
            auto_emoji=auto_emoji, uppercase=uppercase, kinetic_pop=kinetic_pop,
            fit_mode=fit_mode, job_id=job_id,
        )
    except Exception:
        shutil.rmtree(destination_dir, ignore_errors=True)
        raise
    return job


@app.post("/api/jobs/url")
def url_job(payload: URLJob):
    return create_job(
        payload.template, payload.aspect_ratio, payload.clip_count, payload.min_duration, payload.max_duration,
        source_url=payload.source_url, edit_prompt=payload.edit_prompt,
        caption_style=payload.caption_style, caption_mode=payload.caption_mode,
        caption_prompt=payload.caption_prompt, auto_headline=payload.auto_headline,
        auto_emoji=payload.auto_emoji, uppercase=payload.uppercase, kinetic_pop=payload.kinetic_pop,
        fit_mode=payload.fit_mode,
    )


@app.get("/api/jobs")
def list_jobs():
    return sorted((public_job(job) for job in JOBS.values()), key=lambda item: item["created_at"], reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Project not found.")
        return public_job(job)


@app.get("/api/jobs/{job_id}/candidates")
def get_job_candidates(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Project not found.")
    candidates = job.get("candidates") or job.get("clips") or []
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "count": len(candidates),
        "candidates": candidates,
    }


@app.get("/api/jobs/{job_id}/clips/{filename}/timeline")
def get_clip_timeline(job_id: str, filename: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Project not found.")
    clips = job.get("clips", [])
    mp4_name = Path(filename).stem + ".mp4"
    clip = next((c for c in clips if c.get("filename") == mp4_name), None)
    if not clip or "timeline" not in clip:
        candidates = job.get("candidates", [])
        cand = next((c for c in candidates if c.get("filename") == mp4_name or f"cutflow-{c.get('clip_index', 0):02d}.mp4" == mp4_name), None)
        if cand and "timeline" in cand:
            return cand["timeline"]
        raise HTTPException(404, "Timeline not found for clip.")
    return clip["timeline"]


@app.post("/api/jobs/{job_id}/clips/{filename}/export")
def export_custom_clip(job_id: str, filename: str, payload: dict):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Project not found.")
    if Path(filename).name != filename or not re.fullmatch(r"cutflow-\d{2}\.mp4", filename):
        raise HTTPException(400, "Invalid clip filename.")

    timeline = payload.get("timeline")
    if not timeline or not isinstance(timeline, dict):
        raise HTTPException(400, "Missing or invalid timeline payload.")

    clips = job.get("clips", [])
    clip = next((c for c in clips if c.get("filename") == filename), None)
    if not clip:
        raise HTTPException(404, "Clip not found.")

    source_path = job.get("source_path")
    if not source_path or not Path(source_path).is_file():
        raise HTTPException(400, "Source video file is not available on disk.")

    out_dir = OUTPUTS / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = out_dir / f"{Path(filename).stem}.json"
    timeline_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    output_mp4 = out_dir / filename

    start = float(timeline.get("start", clip["start"]))
    end = float(timeline.get("end", clip["end"]))
    aspect = timeline.get("aspect_ratio", job.get("aspect_ratio", "9:16"))
    fit_mode = job.get("fit_mode", "blur")

    # Render with deterministic headless Skia engine
    success = render_clip_headless(
        Path(source_path),
        output_mp4,
        timeline_path,
        start=start,
        end=end,
        aspect=aspect,
        job_id=job_id,
        fit_mode=fit_mode,
    )

    if not success:
        # Fallback to libass if node failed
        ass_path = out_dir / f"{Path(filename).stem}.ass"
        style_key = timeline.get("styling_metadata", {}).get("preset_key", job.get("caption_style", "focus"))
        spec = resolve_caption_spec(style_key)
        ass_content = ass_engine.compile_ass(
            spec,
            words=timeline.get("words", []),
            start=start,
            end=end,
            aspect=aspect,
        )
        ass_path.write_text(ass_content, encoding="utf-8")
        render_clip(Path(source_path), output_mp4, ass_path, start, end, aspect, style_key, fit_mode=fit_mode, job_id=job_id)

    # Update clip metadata in-place
    clip["timeline"] = timeline
    clip["words"] = timeline.get("words", clip.get("words", []))
    clip["size"] = output_mp4.stat().st_size
    clip["start"] = start
    clip["end"] = end
    clip["duration"] = round(end - start, 2)
    update_job(job_id, clips=clips)

    return {
        "ok": True,
        "filename": filename,
        "download_url": clip["download_url"],
        "size": clip["size"],
        "timeline": timeline,
    }


@app.get("/api/jobs/{job_id}/clips/{filename}")
def download_clip(job_id: str, filename: str, resolution: str | None = Query(default=None)):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        if job_id not in JOBS:
            raise HTTPException(404, "Project not found.")
    if Path(filename).name != filename or not re.fullmatch(r"cutflow-\d{2}\.(mp4|srt|ass)", filename):
        raise HTTPException(400, "Invalid clip filename.")
    path = OUTPUTS / job_id / filename
    if not path.is_file():
        if filename.endswith((".srt", ".ass")):
            with LOCK:
                job = JOBS.get(job_id)
            if job:
                mp4_name = Path(filename).stem + ".mp4"
                clip_data = next((c for c in job.get("clips", []) if c.get("filename") == mp4_name), None)
                if clip_data and clip_data.get("text"):
                    words_raw = clip_data.get("text", "").split()
                    duration = max(1.0, clip_data["end"] - clip_data["start"])
                    step = duration / max(1, len(words_raw))
                    words = [{"start": clip_data["start"] + i * step, "end": clip_data["start"] + (i + 1) * step, "word": w} for i, w in enumerate(words_raw)]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if filename.endswith(".srt"):
                        write_srt(path, words, clip_data["start"], clip_data["end"], auto_emoji=job.get("auto_emoji", False), uppercase=job.get("uppercase", False))
                        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=filename)
                    if filename.endswith(".ass"):
                        custom_style = None
                        if job.get("caption_mode") == "prompt" and job.get("caption_prompt"):
                            custom_style = parse_caption_prompt(job["caption_prompt"], clip_data.get("text", ""))
                        spec = resolve_caption_spec(
                            job.get("caption_style", "focus"),
                            custom_style=custom_style,
                            uppercase=job.get("uppercase", False),
                            kinetic_pop=job.get("kinetic_pop", True),
                        )
                        ass_content = ass_engine.compile_ass(
                            spec,
                            words=words,
                            start=clip_data["start"],
                            end=clip_data["end"],
                            aspect=job.get("aspect_ratio", "9:16"),
                            auto_emoji=job.get("auto_emoji", False),
                            emoji_map=EMOJI_MAP,
                            auto_headline=job.get("auto_headline", True),
                            candidate_text=clip_data.get("text", ""),
                            template=job.get("template", "podcast"),
                            extract_headline=extract_headline,
                        )
                        path.write_text(ass_content, encoding="utf-8")
                        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=filename)
        raise HTTPException(404, "Clip is not ready or does not exist.")
    if filename.endswith(".srt"):
        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=filename)
    if filename.endswith(".ass"):
        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=filename)
    if resolution is None or resolution.lower() == "1080":
        return FileResponse(path, media_type="video/mp4", filename=filename)
    if resolution.lower() not in EXPORT_RESOLUTIONS:
        raise HTTPException(400, "Choose 480p, 720p, 1080p, or 2K.")
    with LOCK:
        job = JOBS.get(job_id)
        aspect = job.get("aspect_ratio", "9:16") if job else "9:16"
    width, height = export_dimensions(aspect, resolution.lower())
    export_path = OUTPUTS / job_id / "exports" / f"{Path(filename).stem}-{resolution.lower()}.mp4"
    with EXPORT_LOCK:
        if not export_path.is_file():
            render_export(path, export_path, aspect, resolution.lower())
    export_name = f"{Path(filename).stem}-{resolution.lower()}.mp4"
    return FileResponse(export_path, media_type="video/mp4", filename=export_name, headers={"X-Cutflow-Width": str(width), "X-Cutflow-Height": str(height)})


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Project not found.")
        if job["status"] in {"completed", "failed", "cancelled"}:
            return public_job(job)
        CANCELLED_JOBS.add(job_id)
        proc = ACTIVE_PROCESSES.get(job_id)
        if proc:
            try:
                proc.terminate()
                time.sleep(0.05)
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        job.update(
            status="cancelled",
            stage="Cancelled",
            progress=100,
            message="Processing was cancelled by user.",
            updated_at=time.time(),
        )
        persist_job(job)
        return public_job(job)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Project not found.")
        active_jobs = sum(1 for existing in JOBS.values() if existing.get("status") in {"queued", "processing"})
        if active_jobs >= MAX_ACTIVE_JOBS:
            raise HTTPException(429, f"Cutflow is busy. Wait for active jobs to finish (limit: {MAX_ACTIVE_JOBS}).")

        source_path = job.get("source_path")
        source_url = job.get("source_url")
        if not source_path and not source_url:
            raise HTTPException(400, "Cannot reprocess: source video is missing.")
        if source_path and not Path(source_path).is_file() and not source_url:
            raise HTTPException(400, "Source video file is no longer available on disk.")

        out_dir = OUTPUTS / job_id
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        CANCELLED_JOBS.discard(job_id)
        job.update(
            status="queued",
            progress=0,
            stage="Waiting in queue",
            message="Reprocessing video clip...",
            error=None,
            clips=[],
            updated_at=time.time(),
        )
        persist_job(job)
    POOL.submit(process_job, job_id)
    return public_job(job)


@app.delete("/api/jobs")
def delete_all_jobs():
    with LOCK:
        job_ids = list(JOBS.keys())
        all_ids = set(job_ids) | set(ACTIVE_PROCESSES.keys())
        for jid in all_ids:
            CANCELLED_JOBS.add(jid)
        for proc in list(ACTIVE_PROCESSES.values()):
            try:
                proc.kill()
            except Exception:
                pass
        ACTIVE_PROCESSES.clear()
        JOBS.clear()
        with db_connection() as connection:
            cursor = connection.execute("DELETE FROM jobs")
            deleted_count = cursor.rowcount
            if deleted_count < 0:
                deleted_count = len(job_ids)
            elif deleted_count == 0 and job_ids:
                deleted_count = len(job_ids)
            deleted_count = max(0, deleted_count)

    for directory in (UPLOADS, OUTPUTS):
        if directory.exists():
            for item in directory.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except Exception:
                    pass

    return {"ok": True, "deleted_count": deleted_count}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(404, "Project not found.")
    CANCELLED_JOBS.add(job_id)
    proc = ACTIVE_PROCESSES.get(job_id)
    if proc:
        try:
            proc.kill()
        except Exception:
            pass
    with LOCK:
        job = JOBS.pop(job_id, None)
        with db_connection() as connection:
            connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(404, "Project not found.")
    for directory in (UPLOADS / job_id, OUTPUTS / job_id):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
    return {"ok": True}


app.mount("/assets/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
