from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = Path(os.getenv("CUTFLOW_DATA_DIR", ROOT / "data"))
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
for directory in (UPLOADS, OUTPUTS, FRONTEND):
    directory.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "1024")) * 1024 * 1024
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", str(3 * 60 * 60)))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be", "vimeo.com", "www.vimeo.com", "player.vimeo.com"}
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}

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
}

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("WORKER_CONCURRENCY", "1"))))

app = FastAPI(title="Cutflow", version="0.1.0", description="Template-driven video clipping MVP")


class URLJob(BaseModel):
    source_url: str
    template: str = "podcast"
    aspect_ratio: str = "9:16"
    clip_count: int = Field(default=3, ge=1, le=8)
    min_duration: int = Field(default=20, ge=10, le=60)
    max_duration: int = Field(default=45, ge=15, le=90)


def update_job(job_id: str, **updates) -> None:
    with LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)
            JOBS[job_id]["updated_at"] = time.time()


def run_command(command: list[str], timeout: int = 900) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Command failed")[-1800:]
        raise RuntimeError(detail)
    return completed.stdout


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


def transcribe(path: Path, job_id: str) -> tuple[list[dict], str, str]:
    update_job(job_id, progress=14, stage="Transcribing speech", message="Listening for words and timestamps.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Speech transcription is unavailable. Install backend requirements and restart.") from exc
    model = WhisperModel(WHISPER_MODEL, device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
    segments, info = model.transcribe(str(path), word_timestamps=True, vad_filter=True, beam_size=3)
    words: list[dict] = []
    transcript_parts: list[str] = []
    for segment in segments:
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
        current.append(word)
        if re.search(r"[.!?][\"'’)]?$", word["word"]):
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


def rank_candidates(words: list[dict], template: str, min_duration: int, max_duration: int, video_duration: float, count: int) -> list[dict]:
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
                punctuation_score = min(8, sum(text.count(mark) for mark in "!?") * 2)
                density = len(tokens) / max(1, duration)
                density_score = min(12, density * 3)
                duration_score = max(0, 15 - abs(duration - target) * 0.55)
                context_score = 10 if text[-1:] in ".!?" else 3
                filler_penalty = min(10, sum(tokens.count(filler) for filler in ("um", "uh", "erm")) * 2)
                score = int(max(35, min(96, 40 + hook_bonus + keyword_score + punctuation_score + density_score + duration_score + context_score - filler_penalty)))
                candidates.append({
                    "start": round(start, 2), "end": round(end, 2), "duration": round(duration, 1),
                    "text": text, "score": score, "category": config["label"],
                    "title": make_title(text, template),
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
    selected.sort(key=lambda item: item["start"])
    return selected


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


def write_ass(path: Path, words: list[dict], start: float, end: float, aspect: str) -> None:
    width, height = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}[aspect]
    font_size = 64 if aspect == "9:16" else 48
    margin_v = 190 if aspect == "9:16" else 90
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cutflow,Arial,{font_size},&H00FFFFFF,&H0000FFFF,&H00101010,&H7A101010,-1,0,1,5,1,2,70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    visible = [w for w in words if w["end"] > start and w["start"] < end]
    lines = []
    for index in range(0, len(visible), 5):
        group = visible[index:index + 5]
        if not group:
            continue
        line_start = max(0, group[0]["start"] - start)
        line_end = min(end - start, group[-1]["end"] - start + 0.18)
        if line_end <= line_start:
            continue
        caption = " ".join(w["word"] for w in group)
        caption = caption.replace("{", "(").replace("}", ")").replace("\\", "")
        lines.append(f"Dialogue: 0,{ass_time(line_start)},{ass_time(line_end)},Cutflow,,0,0,0,,{caption}")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str) -> None:
    dimensions = {"9:16": "1080:1920", "1:1": "1080:1080", "16:9": "1920:1080"}
    width, height = dimensions[aspect].split(":")
    ass_path = subtitle_path.resolve().as_posix().replace(":", r"\:")
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},ass='{ass_path}'"
    duration = max(1, end - start)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
        "-vf", vf, "-c:v", "libx264", "-preset", os.getenv("FFMPEG_PRESET", "veryfast"),
        "-crf", "23", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(output),
    ]
    run_command(command, timeout=1200)


def process_job(job_id: str) -> None:
    job = JOBS[job_id]
    source: Path | None = None
    try:
        update_job(job_id, status="processing", progress=4, stage="Preparing video", message="Checking the source video.")
        if job.get("source_url"):
            source = download_source(job["source_url"], job_id)
        else:
            source = Path(job["source_path"])
        if not source.exists():
            raise RuntimeError("The source video could not be found.")
        metadata = probe_video(source)
        update_job(job_id, progress=9, stage="Analyzing audio", message=f"Video is {metadata['duration'] / 60:.1f} minutes long.", video=metadata)
        words, transcript, language = transcribe(source, job_id)
        update_job(job_id, progress=34, stage="Finding highlights", message="Ranking moments against your chosen template.", transcript_preview=transcript[:1200], language=language)
        candidates = rank_candidates(words, job["template"], job["min_duration"], job["max_duration"], metadata["duration"], job["clip_count"])
        if not candidates:
            raise RuntimeError("No usable moments were found. Try a longer video with clear speech or adjust the duration range.")
        output_dir = OUTPUTS / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        completed = []
        for index, candidate in enumerate(candidates, start=1):
            update_job(job_id, progress=35 + int((index - 1) / len(candidates) * 60), stage=f"Rendering clip {index} of {len(candidates)}", message=f"Creating {job['aspect_ratio']} video with captions.")
            clip_name = f"cutflow-{index:02d}.mp4"
            output = output_dir / clip_name
            ass_path = output_dir / f"cutflow-{index:02d}.ass"
            write_ass(ass_path, words, candidate["start"], candidate["end"], job["aspect_ratio"])
            render_clip(source, output, ass_path, candidate["start"], candidate["end"], job["aspect_ratio"])
            completed.append({
                **candidate,
                "id": str(uuid.uuid4()),
                "filename": clip_name,
                "download_url": f"/api/jobs/{job_id}/clips/{clip_name}",
                "size": output.stat().st_size,
                "aspect_ratio": job["aspect_ratio"],
            })
            update_job(job_id, clips=completed, progress=35 + int(index / len(candidates) * 60))
        update_job(job_id, status="completed", progress=100, stage="Ready to download", message=f"Created {len(completed)} clips.", clips=completed, transcript_preview=transcript[:1200], language=language)
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, stage="Needs attention", error=str(exc)[:1500], message="Processing failed. Review the error and try again.")
    finally:
        # Keep source files for debugging and future re-renders; user data is local to this instance.
        pass


def create_job(template: str, aspect_ratio: str, clip_count: int, min_duration: int, max_duration: int, source_path: str | None = None, source_url: str | None = None) -> dict:
    if template not in TEMPLATES:
        raise HTTPException(400, "Choose a valid template.")
    if aspect_ratio not in {"9:16", "1:1", "16:9"}:
        raise HTTPException(400, "Choose a valid aspect ratio.")
    if not (10 <= min_duration < max_duration <= 90):
        raise HTTPException(400, "Clip duration must be between 10 and 90 seconds, with minimum below maximum.")
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id, "status": "queued", "progress": 0, "stage": "Waiting in queue",
        "message": "Your video is queued for analysis.", "template": template,
        "template_label": TEMPLATES[template]["label"], "aspect_ratio": aspect_ratio,
        "clip_count": clip_count, "min_duration": min_duration, "max_duration": max_duration,
        "source_path": source_path, "source_url": source_url, "clips": [],
        "created_at": time.time(), "updated_at": time.time(),
    }
    with LOCK:
        JOBS[job_id] = job
    POOL.submit(process_job, job_id)
    return public_job(job)


def public_job(job: dict) -> dict:
    hidden = {"source_path"}
    return {key: value for key, value in job.items() if key not in hidden}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "cutflow", "version": "0.1.0"}


@app.get("/api/templates")
def templates():
    return [{"id": key, "label": value["label"], "description": value["description"]} for key, value in TEMPLATES.items()]


@app.post("/api/jobs/upload")
async def upload_job(
    file: UploadFile = File(...),
    template: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_count: int = Form(3),
    min_duration: int = Form(20),
    max_duration: int = Form(45),
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
    job = create_job(template, aspect_ratio, clip_count, min_duration, max_duration, source_path=str(destination))
    return job


@app.post("/api/jobs/url")
def url_job(payload: URLJob):
    return create_job(payload.template, payload.aspect_ratio, payload.clip_count, payload.min_duration, payload.max_duration, source_url=payload.source_url)


@app.get("/api/jobs")
def list_jobs():
    return sorted((public_job(job) for job in JOBS.values()), key=lambda item: item["created_at"], reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Project not found.")
        return public_job(job)


@app.get("/api/jobs/{job_id}/clips/{filename}")
def download_clip(job_id: str, filename: str):
    if Path(filename).name != filename or not re.fullmatch(r"cutflow-\d{2}\.mp4", filename):
        raise HTTPException(400, "Invalid clip filename.")
    path = OUTPUTS / job_id / filename
    if not path.is_file():
        raise HTTPException(404, "Clip is not ready or does not exist.")
    return FileResponse(path, media_type="video/mp4", filename=filename)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    with LOCK:
        job = JOBS.pop(job_id, None)
    if not job:
        raise HTTPException(404, "Project not found.")
    for directory in (UPLOADS / job_id, OUTPUTS / job_id):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
    return {"ok": True}


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
