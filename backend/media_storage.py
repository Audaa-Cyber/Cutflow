"""Validated media edits and atomic artifact publication.

Job state holds a revision pointer; files are complete before that pointer changes.
The application supplies render/storage functions to keep transport separate.
"""
from __future__ import annotations

import copy
import json
import math
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def validate_timeline(payload: dict, clip: dict, job: dict, duration: float) -> dict:
    timeline = payload.get('timeline') if isinstance(payload, dict) else None
    if not isinstance(timeline, dict) or not timeline:
        raise HTTPException(400, 'Missing or invalid timeline payload.')
    try:
        encoded = json.dumps(timeline, allow_nan=False)
        if len(encoded.encode('utf-8')) > 2 * 1024 * 1024:
            raise ValueError()

        def validate_json(value, depth=0):
            if depth > 20:
                raise ValueError()
            if isinstance(value, dict):
                if len(value) > 1000:
                    raise ValueError()
                for key, item in value.items():
                    if not isinstance(key, str) or len(key) > 100:
                        raise ValueError()
                    validate_json(item, depth + 1)
            elif isinstance(value, list):
                if len(value) > 5000:
                    raise ValueError()
                for item in value:
                    validate_json(item, depth + 1)
            elif isinstance(value, str) and len(value) > 10000:
                raise ValueError()
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(value) or abs(value) > 1000000000:
                    raise ValueError()
        validate_json(timeline)

        def number(value):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError()
            return float(value)

        start = number(timeline.get('start', clip['start']))
        end = number(timeline.get('end', clip['end']))
        if start < 0 or end <= start or end > duration + 0.001 or end - start > 300:
            raise ValueError()
        aspect = timeline.get('aspect_ratio', job.get('aspect_ratio', '9:16'))
        if aspect not in {'9:16', '1:1', '16:9'}:
            raise ValueError()
        metadata = timeline.get('styling_metadata', {})
        from backend.captions.presets import PRESETS
        if not isinstance(metadata, dict) or metadata.get('preset_key', job.get('caption_style', 'focus')) not in PRESETS:
            raise ValueError()

        def validate_words(words):
            if not isinstance(words, list) or len(words) > 2000:
                raise ValueError()
            for word in words:
                if not isinstance(word, dict):
                    raise ValueError()
                w_start, w_end = number(word.get('start')), number(word.get('end'))
                text = word.get('text', word.get('word', ''))
                if not isinstance(text, str) or len(text) > 1000 or w_start < start or w_end > end or w_end <= w_start:
                    raise ValueError()
        validate_words(timeline.get('words', []))
        for collection in ('phrases', 'stickers', 'camera_events', 'audio_sfx'):
            if not isinstance(timeline.get(collection, []), list):
                raise ValueError()
            for event in timeline.get(collection, []):
                if not isinstance(event, dict):
                    raise ValueError()
                if collection == 'phrases':
                    validate_words(event.get('words', []))
                    if number(event.get('start')) < start or number(event.get('end')) > end:
                        raise ValueError()
                elif collection == 'audio_sfx':
                    if not re.fullmatch(r'[a-z0-9_-]{1,40}', event.get('type', '')):
                        raise ValueError()
                    if not start * 1000 <= number(event.get('timestamp_ms')) <= end * 1000:
                        raise ValueError()
                    if not 0 <= number(event.get('volume', 0.75)) <= 2:
                        raise ValueError()
                elif collection == 'stickers':
                    for key in ('category', 'asset'):
                        if key in event and (not isinstance(event[key], str) or not re.fullmatch(r'[a-z0-9_.-]{1,80}', event[key]) or '..' in event[key]):
                            raise ValueError()
        result = copy.deepcopy(timeline)
        result.update(start=start, end=end, aspect_ratio=aspect)
        return result
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise HTTPException(400, 'Timeline contains invalid ranges, styling, or caption data.') from None


def find_clip(api, job_id: str, filename: str) -> tuple[dict, dict]:
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Project not found.')
    if not re.fullmatch(r'cutflow-\d{2}\.(mp4|srt|ass)', filename):
        raise HTTPException(400, 'Invalid clip filename.')
    with api.LOCK:
        job = api.JOBS.get(job_id)
        if not job:
            raise HTTPException(404, 'Project not found.')
        master = Path(filename).stem + '.mp4'
        clip = next((c for c in job.get('clips', []) if c.get('filename') == master), None)
        if not clip:
            raise HTTPException(404, 'Clip not found.')
        return job, clip


def export_clip(api, job_id: str, filename: str, payload: dict):
    if not filename.endswith('.mp4'):
        raise HTTPException(400, 'Invalid clip filename.')
    # Serialize expensive edits and quality generation for the single-instance design.
    with api.EXPORT_LOCK:
        job, clip = find_clip(api, job_id, filename)
        api.check_job_cancelled(job_id)
        # Reject malformed data before performing remote source requests.
        known_duration = float(job.get('video', {}).get('duration') or clip['end'])
        timeline = validate_timeline(payload, clip, job, known_duration)
        source = api.resolve_job_source(job)
        if not job.get('video', {}).get('duration'):
            timeline = validate_timeline(payload, clip, job, api.probe_video(source)['duration'])
        revision = uuid.uuid4().hex
        directory = api.OUTPUTS / job_id / 'revisions' / revision
        directory.mkdir(parents=True)
        stem = Path(filename).stem
        updated = copy.deepcopy(clip)
        updated.update(timeline=timeline, words=timeline.get('words', []), start=timeline['start'],
                       end=timeline['end'], duration=round(timeline['end'] - timeline['start'], 3),
                       aspect_ratio=timeline['aspect_ratio'], artifact_revision=revision,
                       text=' '.join(w.get('text', w.get('word', '')) for w in timeline.get('words', [])),
                       **api.clip_media_urls(job_id, filename))
        uploaded = {}
        committed = False
        try:
            timeline_path = directory / (stem + '.json')
            timeline_path.write_text(json.dumps(timeline, indent=2, allow_nan=False), encoding='utf-8')
            api.write_clip_subtitles(job, updated, directory)
            output = directory / filename
            canvas = api.render_clip_headless(source, output, timeline_path, timeline['start'], timeline['end'],
                timeline['aspect_ratio'], job_id=job_id, fit_mode=job.get('fit_mode', 'blur'))
            api.check_job_cancelled(job_id)
            if not canvas:
                api.render_clip(source, output, directory / (stem + '.ass'), timeline['start'], timeline['end'],
                    timeline['aspect_ratio'], timeline.get('styling_metadata', {}).get('preset_key', job.get('caption_style', 'focus')),
                    template=job.get('template', 'podcast'), fit_mode=job.get('fit_mode', 'blur'), job_id=job_id)
            api.render_clean_preview(source, directory / (stem + '.preview.mp4'), timeline['start'], timeline['end'],
                timeline['aspect_ratio'], job_id=job_id, fit_mode=job.get('fit_mode', 'blur'), template=job.get('template', 'podcast'))
            api.check_job_cancelled(job_id)
            required_files = [filename, stem + '.ass', stem + '.srt', stem + '.json', stem + '.preview.mp4']
            for name in required_files:
                path = directory / name
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError('Renderer did not produce a complete clip.')
            uploaded = api.upload_clip_artifacts(job_id, updated, directory, revision)
            updated.update(artifacts=uploaded, renderer='canvas' if canvas else 'ass', size=output.stat().st_size)
            with api.LOCK:
                api.check_job_cancelled(job_id)
                # A retry or delete during rendering must not publish stale work.
                if api.JOBS[job_id] is not job or clip not in job.get('clips', []):
                    raise api.JobCancelledException('Project changed during export.')
                new_job = copy.deepcopy(job)
                new_job['clips'] = [updated if c is clip else copy.deepcopy(c) for c in job['clips']]
                new_job['updated_at'] = time.time()
                retired = list(new_job.get('retired_artifacts', []))
                retired.extend(clip.get('artifacts', {}).values())
                new_job['retired_artifacts'] = list(set(retired))
                api.persist_job(new_job)
                job.update(new_job)
                committed = True
            cache = api.OUTPUTS / job_id / 'exports'
            if cache.is_dir():
                for path in cache.glob(stem + '-*.mp4'):
                    path.unlink(missing_ok=True)
            public_clip = next(c for c in api.public_job(job)['clips'] if c['filename'] == filename)
            return {'ok': True, **public_clip}
        except api.JobCancelledException:
            raise HTTPException(409, 'Export was cancelled or the project changed.') from None
        finally:
            if not committed:
                for location in uploaded.values():
                    api.blob_delete(location)
                shutil.rmtree(directory, ignore_errors=True)


def recover_artifact(api, job: dict, clip: dict, filename: str, kind: str) -> Path:
    path = api.artifact_directory(job, clip) / filename
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    cloud = clip.get('artifacts', {}).get(kind)
    if not cloud and kind == 'mp4' and clip.get('download_url', '').startswith('https://'):
        cloud = clip['download_url']  # Migration of an existing cloud project.
    if cloud:
        pending = path.with_name(path.name + '.' + uuid.uuid4().hex + '.part')
        try:
            api.blob_download(cloud, pending)
            api.check_job_cancelled(job['id'])
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
    elif kind in {'srt', 'ass'} and (clip.get('timeline') or clip.get('words')):
        api.write_clip_subtitles(job, clip, path.parent)
    elif kind == 'preview':
        pending = path.with_name(uuid.uuid4().hex + '.mp4')
        try:
            api.render_clean_preview(api.resolve_job_source(job), pending, clip['start'], clip['end'],
                clip.get('aspect_ratio', job.get('aspect_ratio', '9:16')), job_id=job['id'],
                fit_mode=job.get('fit_mode', 'blur'), template=job.get('template', 'podcast'))
            api.check_job_cancelled(job['id'])
            if not pending.is_file() or pending.stat().st_size == 0:
                raise HTTPException(404, 'Preview is not ready.')
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
    if not path.is_file():
        raise HTTPException(404, 'Clip is not ready or does not exist.')
    return path


def download(api, job_id: str, filename: str, resolution: str | None = None):
    # FastAPI's Query default is an object when internal helpers are called directly.
    resolution = resolution if isinstance(resolution, str) else None
    if resolution is not None and resolution.lower() not in api.EXPORT_RESOLUTIONS:
        raise HTTPException(400, 'Choose 480p, 720p, 1080p, or 2K.')
    job, clip = find_clip(api, job_id, filename)
    kind = Path(filename).suffix[1:]
    path = api.artifact_directory(job, clip) / filename
    if not path.is_file():
        with api.EXPORT_LOCK:
            path = recover_artifact(api, job, clip, filename, kind)
    if kind in {'srt', 'ass'}:
        return FileResponse(path, media_type='text/plain; charset=utf-8', filename=filename)
    if resolution is None or resolution.lower() == '1080':
        return FileResponse(path, media_type='video/mp4', filename=filename)
    resolution = resolution.lower()
    aspect = clip.get('aspect_ratio', job.get('aspect_ratio', '9:16'))
    width, height = api.export_dimensions(aspect, resolution)
    export_name = f'{Path(filename).stem}-{resolution}.mp4'
    cache_dir = api.OUTPUTS / job_id / 'exports'
    if clip.get('artifact_revision'):
        cache_dir /= clip['artifact_revision']
    export_path = cache_dir / export_name
    with api.EXPORT_LOCK:
        if not export_path.is_file():
            cache_dir.mkdir(parents=True, exist_ok=True)
            pending = cache_dir / (uuid.uuid4().hex + '.mp4')
            try:
                api.render_export(path, pending, aspect, resolution)
                api.check_job_cancelled(job_id)
                pending.replace(export_path)
            finally:
                pending.unlink(missing_ok=True)
        return FileResponse(export_path, media_type='video/mp4', filename=export_name,
            headers={'X-Cutflow-Width': str(width), 'X-Cutflow-Height': str(height)})


def preview(api, job_id: str, filename: str):
    if not filename.endswith('.mp4'):
        raise HTTPException(400, 'Invalid clip filename.')
    job, clip = find_clip(api, job_id, filename)
    preview_name = Path(filename).stem + '.preview.mp4'
    path = api.artifact_directory(job, clip) / preview_name
    if not path.is_file():
        with api.EXPORT_LOCK:
            path = recover_artifact(api, job, clip, preview_name, 'preview')
    return FileResponse(path, media_type='video/mp4')
