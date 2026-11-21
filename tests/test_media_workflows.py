"""Media regressions: preserve private sources, timing and committed artifacts."""
import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from tests._isolation import isolate_storage

isolate_storage()
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import contextmanager

from fastapi import HTTPException

# A focused invocation must never open the user's ordinary application database.
import backend.app as media


class MediaWorkflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(media, 'UPLOADS', root / 'uploads'),
                        patch.object(media, 'OUTPUTS', root / 'outputs'),
                        patch.object(media, 'persist_job'), patch.object(media, 'blob_enabled', return_value=False)]
        for p in self.patches:
            p.start()
        self.addCleanup(self.tmp.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)
        self.addCleanup(media.JOBS.clear)
        self.addCleanup(media.CANCELLED_JOBS.clear)
        self.addCleanup(media.WORKER_FUTURES.clear)
        self.source = root / 'source.mp4'
        self.source.write_bytes(b'source')
        self.job = {'id': 'a' * 32, 'created_at': 1, 'updated_at': 1, 'status': 'completed',
                    'source_path': str(self.source), 'video': {'duration': 120},
                    'aspect_ratio': '9:16', 'caption_style': 'focus', 'template': 'podcast',
                    'clips': [{'filename': 'cutflow-01.mp4', 'start': 60, 'end': 65,
                               'download_url': '/api/jobs/' + 'a' * 32 + '/clips/cutflow-01.mp4',
                               'text': 'original', 'timeline': {'start': 60, 'end': 65, 'words': [
                                   {'start': 61.25, 'end': 61.70, 'text': 'Exactly.'}]}}]}
        media.JOBS[self.job['id']] = self.job
        self.out = media.OUTPUTS / self.job['id']
        self.out.mkdir(parents=True)
        (self.out / 'cutflow-01.mp4').write_bytes(b'original master')
        self.timeline = {'start': 60, 'end': 65, 'aspect_ratio': '9:16', 'words': [
            {'start': 61.25, 'end': 61.70, 'text': 'Edited.'}], 'phrases': [],
            'styling_metadata': {'preset_key': 'focus'}}

    def export(self, timeline=None):
        return media.export_custom_clip(self.job['id'], 'cutflow-01.mp4', {'timeline': timeline or self.timeline})

    @staticmethod
    def rendered(source, output, *args, **kwargs):
        output.write_bytes(b'new captioned master')
        return True

    @staticmethod
    def clean(source, output, *args, **kwargs):
        output.write_bytes(b'clean video')

    def test_url_source_is_persisted_and_reused_for_export(self):
        self.job.update(source_path=None, source_url='https://example.org/video.mp4')
        with patch.object(media, 'download_source', return_value=self.source):
            resolved = media.resolve_job_source(self.job)
        self.assertEqual(resolved, self.source)
        self.assertEqual(self.job['source_path'], str(self.source))
        with patch.object(media, 'download_source', side_effect=AssertionError('source should be reused')):
            self.assertEqual(media.resolve_job_source(self.job), self.source)

    def test_generated_zero_duration_words_remain_editable_inside_clip_bounds(self):
        from backend.captions.presets import PRESETS
        from backend.captions.timeline import build_kinetic_timeline
        timeline = build_kinetic_timeline([
            {'word': 'money', 'start': 61.2, 'end': 61.2},
            {'word': 'end', 'start': 64.995, 'end': 64.995}],
            60, 65, PRESETS['focus'])
        for word in timeline['words']:
            self.assertGreater(word['end'], word['start'])
            self.assertLessEqual(word['end'], 65)
            self.assertEqual(word['end'], word['end_ms'] / 1000)
        with patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean):
            response = self.export(timeline)
        self.assertTrue(response['ok'])

    def test_blob_source_recovers_local_copy_for_retry_and_export(self):
        self.job['source_path'] = 'blob:https://private.example/source'
        def fetch(location, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b'cloud source')
        with patch.object(media, 'blob_download', side_effect=fetch):
            path = media.resolve_job_source(self.job)
        self.assertEqual(path.read_bytes(), b'cloud source')
        self.assertTrue(media.source_available(self.job))
        self.assertEqual(self.job['source_blob_url'], 'https://private.example/source')
        path.unlink()
        with patch.object(media, 'blob_download', side_effect=fetch):
            self.assertEqual(media.resolve_job_source(self.job).read_bytes(), b'cloud source')

    def test_url_source_upload_cancel_cleans_unattached_cloud_source(self):
        self.job.update(source_path=None, source_url='https://example.org/video.mp4')
        removed = []
        def upload(path, remote):
            media.CANCELLED_JOBS.add(self.job['id'])
            return 'https://private.example/unattached-source'
        with patch.object(media, 'download_source', return_value=self.source), patch.object(media, 'blob_enabled', return_value=True), patch.object(media, 'blob_upload', side_effect=upload), patch.object(media, 'blob_delete', side_effect=removed.append):
            with self.assertRaises(media.JobCancelledException):
                media.resolve_job_source(self.job)
        self.assertEqual(removed, ['https://private.example/unattached-source'])

    def test_failed_preview_recovery_does_not_cache_partial_video(self):
        def interrupted(source, output, *args, **kwargs):
            output.write_bytes(b'partial preview')
            raise media.JobCancelledException()
        with patch.object(media, 'render_clean_preview', side_effect=interrupted):
            with self.assertRaises((media.JobCancelledException, HTTPException)):
                media.preview_clip(self.job['id'], 'cutflow-01.mp4')
        self.assertFalse((self.out / 'cutflow-01.preview.mp4').exists())

    def test_cloud_cleanup_removes_source_and_all_variants(self):
        self.job['source_path'] = 'blob:https://private.example/source'
        self.job['clips'][0]['artifacts'] = {'mp4': 'https://private.example/master', 'srt': 'https://private.example/sub'}
        removed = []
        with patch.object(media, 'blob_delete', side_effect=removed.append):
            media.cleanup_job_cloud(self.job)
        self.assertEqual(set(removed), {'https://private.example/source', 'https://private.example/master', 'https://private.example/sub'})

    def test_cloud_cleanup_reports_failed_deletions_without_exposing_locations(self):
        self.job['source_blob_url'] = 'https://private.example/source'
        self.job['clips'][0]['artifacts'] = {'mp4': 'https://private.example/master'}
        with patch.object(media, 'blob_delete', side_effect=[True, False]):
            failures = media.cleanup_job_cloud(self.job)
        self.assertEqual(failures, 1)

    def test_retry_retains_old_cloud_artifacts_for_deletion_after_restart(self):
        old_artifacts = {'mp4': 'https://private.example/master', 'srt': 'https://private.example/sub',
                         'ass': 'https://private.example/ass', 'timeline': 'https://private.example/timeline',
                         'preview': 'https://private.example/preview'}
        self.job['clips'][0]['artifacts'] = old_artifacts
        self.job['clips'][0]['download_url'] = 'https://private.example/legacy'
        with patch.object(media.POOL, 'submit'), patch.object(media, 'check_job_quota'):
            media.retry_job(self.job['id'])
        # Cleanup inventory must survive JSON persistence and have no live clips.
        restored = json.loads(json.dumps(self.job))
        removed = []
        with patch.object(media, 'blob_delete', side_effect=removed.append):
            media.cleanup_job_cloud(restored)
        self.assertEqual(restored['clips'], [])
        self.assertEqual(set(removed), set(old_artifacts.values()) | {'https://private.example/legacy'})

    def test_subtitle_recovery_uses_exact_timeline_times_and_edited_text(self):
        response = media.download_clip(self.job['id'], 'cutflow-01.srt', resolution=None)
        body = Path(response.path).read_text(encoding='utf-8')
        self.assertIn('00:00:01,250 --> 00:00:01,840', body)
        self.assertIn('Exactly.', body)
        self.assertNotIn('original', body)

    def test_cloud_master_is_proxied_before_quality_conversion(self):
        (self.out / 'cutflow-01.mp4').unlink()
        self.job['clips'][0]['artifacts'] = {'mp4': 'https://private.example/master'}
        def fetch(location, destination):
            destination.write_bytes(b'cloud master')
        def quality(source, output, aspect, resolution):
            self.assertEqual(source.read_bytes(), b'cloud master')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b'480 video')
        with patch.object(media, 'blob_download', side_effect=fetch), patch.object(media, 'render_export', side_effect=quality):
            response = media.download_clip(self.job['id'], 'cutflow-01.mp4', resolution='480')
        self.assertEqual(Path(response.path).read_bytes(), b'480 video')
        self.assertEqual(response.status_code, 200)

    def test_headless_cancellation_propagates_instead_of_fallback(self):
        with patch.object(media.shutil, 'which', return_value='node'), patch.object(media, 'run_command', side_effect=media.JobCancelledException()):
            with self.assertRaises(media.JobCancelledException):
                media.render_clip_headless(self.source, self.out / 'x.mp4', self.out / 'x.json', 60, 65, '9:16')

    def test_export_failure_preserves_master_timeline_and_metadata(self):
        before = copy.deepcopy(self.job['clips'])
        (self.out / 'cutflow-01.json').write_text('original timeline')
        def fail(source, output, *args, **kwargs):
            output.write_bytes(b'partial broken video')
            raise RuntimeError('renderer failed')
        with patch.object(media, 'render_clip_headless', side_effect=fail):
            with self.assertRaises((RuntimeError, HTTPException)):
                self.export()
        self.assertEqual((self.out / 'cutflow-01.mp4').read_bytes(), b'original master')
        self.assertEqual((self.out / 'cutflow-01.json').read_text(), 'original timeline')
        self.assertEqual(self.job['clips'], before)

    def test_export_missing_preview_never_publishes_incomplete_revision(self):
        with patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', return_value=None):
            with self.assertRaises((RuntimeError, HTTPException)):
                self.export()
        response = media.download_clip(self.job['id'], 'cutflow-01.mp4', resolution=None)
        self.assertEqual(Path(response.path).read_bytes(), b'original master')

    def test_cloud_upload_failure_preserves_original_and_cleans_partial_uploads(self):
        removed = []
        def upload(path, remote):
            if path.suffix == '.srt':
                raise RuntimeError('storage failure')
            return 'https://private.example/new-master'
        with patch.object(media, 'blob_enabled', return_value=True), patch.object(media, 'blob_upload', side_effect=upload), patch.object(media, 'blob_delete', side_effect=removed.append), patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean):
            with self.assertRaises((RuntimeError, HTTPException)):
                self.export()
        self.assertEqual(removed, ['https://private.example/new-master'])
        response = media.download_clip(self.job['id'], 'cutflow-01.mp4', resolution=None)
        self.assertEqual(Path(response.path).read_bytes(), b'original master')

    def test_persistence_failure_keeps_previous_revision_visible(self):
        with patch.object(media, 'persist_job', side_effect=RuntimeError('database failure')), patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean):
            with self.assertRaises((RuntimeError, HTTPException)):
                self.export()
        self.assertNotIn('artifact_revision', self.job['clips'][0])
        response = media.download_clip(self.job['id'], 'cutflow-01.mp4', resolution=None)
        self.assertEqual(Path(response.path).read_bytes(), b'original master')

    def test_cancelled_export_preserves_original_artifacts(self):
        (self.out / 'cutflow-01.json').write_text('original timeline')
        with patch.object(media, 'render_clip_headless', side_effect=media.JobCancelledException()):
            with self.assertRaises((media.JobCancelledException, HTTPException)):
                self.export()
        self.assertEqual((self.out / 'cutflow-01.mp4').read_bytes(), b'original master')
        self.assertEqual((self.out / 'cutflow-01.json').read_text(), 'original timeline')

    def test_cancel_endpoint_stops_completed_project_export(self):
        def cancelled(source, output, *args, **kwargs):
            media.cancel_job(self.job['id'])
            output.write_bytes(b'partial export')
            return True
        with patch.object(media, 'render_clip_headless', side_effect=cancelled):
            with self.assertRaises(HTTPException) as error:
                self.export()
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual((self.out / 'cutflow-01.mp4').read_bytes(), b'original master')
        self.assertNotIn(self.job['id'], media.ACTIVE_EXPORTS)

    def test_cancelled_job_export_returns_conflict_before_source_resolution(self):
        self.job['status'] = 'cancelled'
        with self.assertRaises(HTTPException) as error:
            self.export()
        self.assertEqual(error.exception.status_code, 409)

    def test_download_serves_previous_revision_while_an_edit_is_rendering(self):
        results = []
        def during_render(source, output, *args, **kwargs):
            def read():
                response = media.download_clip(self.job['id'], 'cutflow-01.mp4', resolution=None)
                results.append(Path(response.path).read_bytes())
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            reader.join(timeout=1)
            self.assertEqual(results, [b'original master'])
            return self.rendered(source, output, *args, **kwargs)
        with patch.object(media, 'render_clip_headless', side_effect=during_render), patch.object(media, 'render_clean_preview', side_effect=self.clean):
            self.export()

    def test_export_reports_canvas_and_invalidates_quality_cache(self):
        cache = self.out / 'exports'
        cache.mkdir()
        (cache / 'cutflow-01-480.mp4').write_bytes(b'old variant')
        with patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean, create=True):
            response = self.export()
        self.assertEqual(response['renderer'], 'canvas')
        self.assertFalse((cache / 'cutflow-01-480.mp4').exists())
        preview = media.preview_clip(self.job['id'], 'cutflow-01.mp4')
        self.assertEqual(Path(preview.path).read_bytes(), b'clean video')
        self.assertTrue(response['preview_url'].startswith('/api/'))
        subtitle = media.download_clip(self.job['id'], 'cutflow-01.srt', resolution=None)
        self.assertIn('EDITED.', Path(subtitle.path).read_text().upper())

    def test_export_reports_ass_fallback_and_keeps_text_field(self):
        with patch.object(media, 'render_clip_headless', return_value=False), patch.object(media, 'render_clip', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean, create=True):
            response = self.export()
        self.assertEqual(response['renderer'], 'ass')
        subtitle = media.download_clip(self.job['id'], 'cutflow-01.ass', resolution=None)
        self.assertIn('EDITED.', Path(subtitle.path).read_text().upper())

    def test_export_cloud_uploads_current_artifacts_without_public_urls(self):
        self.job['clips'][0]['artifacts'] = {'mp4': 'https://private.example/old'}
        uploaded = {}
        def upload(path, remote):
            uploaded[path.suffix if '.preview.' not in path.name else 'preview'] = path.read_bytes()
            return 'https://private.example/' + remote
        with patch.object(media, 'blob_enabled', return_value=True), patch.object(media, 'blob_upload', side_effect=upload), patch.object(media, 'blob_delete'), patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean, create=True):
            response = self.export()
        self.assertEqual(uploaded['.mp4'], b'new captioned master')
        self.assertEqual(uploaded['preview'], b'clean video')
        self.assertEqual(set(uploaded), {'.mp4', '.srt', '.ass', '.json', 'preview'})
        self.assertTrue(response['download_url'].startswith('/api/'))
        self.assertNotIn('artifacts', response)

    def test_invalid_export_ranges_and_payloads_are_rejected(self):
        changes = [{'start': -1}, {'end': 121}, {'start': 65}, {'start': 'bad'}, {'end': float('nan')},
                   {'aspect_ratio': '4:3'}, {'words': 'bad'}, {'words': [{'text': 'bad', 'start': 60, 'end': 59}]},
                   {'styling_metadata': {'preset_key': 'unknown'}}, {'words': [{'text': 'x' * 10001, 'start': 60, 'end': 61}]}]
        changes += [{'audio_sfx': [{'type': '../../secret', 'timestamp_ms': 61000}]},
                    {'stickers': [{'category': 'money', 'asset': '../../secret.svg'}]},
                    {'phrases': [{'start': 61, 'end': 62, 'words': 'invalid'}]}]
        with patch.object(media, 'render_clip_headless', side_effect=self.rendered), patch.object(media, 'render_clean_preview', side_effect=self.clean, create=True):
            for index, change in enumerate(changes):
                with self.subTest(case=index):
                    timeline = {**self.timeline, **change}
                    with self.assertRaises(HTTPException) as error:
                        self.export(timeline)
                    self.assertEqual(error.exception.status_code, 400)

    def test_clean_preview_uses_same_clip_range_without_subtitle_filter(self):
        commands = []
        with patch.object(media, 'probe_video', return_value={'width': 1920, 'height': 1080}), patch.object(media, 'run_command', side_effect=lambda cmd, **kwargs: commands.append(cmd)):
            media.render_clean_preview(self.source, self.out / 'preview.mp4', 60, 65, '9:16', job_id=self.job['id'])
        command = commands[-1]
        self.assertEqual(command[command.index('-ss') + 1], '60.000')
        self.assertEqual(command[command.index('-t') + 1], '5.000')
        graph = command[command.index('-filter_complex') + 1]
        self.assertIn('boxblur', graph)
        self.assertNotIn("ass=", graph)

    def test_blob_upload_uses_private_storage_and_streams_source(self):
        def put(pathname, body, **options):
            self.assertEqual(options['access'], 'private')
            self.assertEqual(options['content_length'], 6)
            self.assertTrue(hasattr(body, 'read'))
            self.assertEqual(body.read(), b'source')
            return SimpleNamespace(url='https://private.example/source')
        with patch.object(media, '_blob_sync', SimpleNamespace(put_blob=put)):
            self.assertEqual(media.blob_upload(self.source, 'source'), 'https://private.example/source')

    def test_blob_download_streams_private_chunks_to_disk(self):
        @contextmanager
        def stream(location, **options):
            self.assertEqual(options['access'], 'private')
            yield iter([b'video', b' chunks'])
        destination = self.out / 'download.mp4'
        with patch.object(media, '_blob_sync', SimpleNamespace(stream_blob=stream)):
            media.blob_download('https://private.example/source', destination)
        self.assertEqual(destination.read_bytes(), b'video chunks')

    def test_processing_publishes_clean_preview_and_private_current_artifacts(self):
        self.job.update(status='queued', clip_count=1, min_duration=10, max_duration=20,
                        template_label=media.TEMPLATES['podcast']['label'])
        words = [{'start': 61.25, 'end': 61.70, 'word': 'Exactly.'}]
        candidate = {'start': 60, 'end': 65, 'text': 'Exactly.', 'title': 'Exact timing'}
        uploads = []
        def upload(path, remote):
            uploads.append(path.name)
            return 'https://private.example/' + remote
        with patch.object(media, 'transcribe', return_value=(words, 'Exactly.', 'en')), \
             patch.object(media, 'probe_video', return_value={'duration': 120, 'width': 1920, 'height': 1080}), \
             patch.object(media, 'detect_scene_changes', return_value=[]), \
             patch.object(media, 'rank_candidates', return_value=[candidate]), \
             patch.object(media, 'render_clip_headless', side_effect=self.rendered), \
             patch.object(media, 'render_clean_preview', side_effect=self.clean, create=True), \
             patch.object(media, 'blob_enabled', return_value=True), \
             patch.object(media, 'blob_upload', side_effect=upload):
            media.process_job(self.job['id'])
        self.assertEqual(self.job['status'], 'completed', self.job.get('error'))
        clip = self.job['clips'][0]
        self.assertIn('preview_url', clip)
        self.assertEqual(clip['renderer'], 'canvas')
        self.assertTrue(clip['download_url'].startswith('/api/'))
        self.assertEqual(set(uploads), {'cutflow-01.mp4', 'cutflow-01.srt', 'cutflow-01.ass', 'cutflow-01.json', 'cutflow-01.preview.mp4'})


if __name__ == '__main__':
    unittest.main()
