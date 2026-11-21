"""HTTP regressions for the account-free shared project workspace."""
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tests._isolation import isolate_storage

os.environ.setdefault('CUTFLOW_ALLOWED_ORIGINS', 'https://cutflow.example')
isolate_storage()
from starlette.testclient import TestClient
import backend.app as backend


class SharedProjectAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='cutflow-shared-projects-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, value in {'DB_PATH': root / 'jobs.sqlite3', 'UPLOADS': root / 'uploads', 'OUTPUTS': root / 'outputs'}.items():
            replacement = patch.object(backend, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        for name in ('JOBS', 'WORKER_FUTURES', 'ACTIVE_PROCESSES'):
            value = getattr(backend, name)
            saved = value.copy()
            value.clear()
            def restore(value=value, saved=saved):
                value.clear()
                value.update(saved)
            self.addCleanup(restore)
        self.addCleanup(backend.CANCELLED_JOBS.clear)
        backend.load_persisted_jobs()
        submit = patch.object(backend.POOL, 'submit')
        submit.start()
        self.addCleanup(submit.stop)
        self.client = TestClient(backend.app)
        self.addCleanup(self.client.close)

    def make_job(self):
        response = self.client.post('/api/jobs/url', json={'source_url': 'https://youtu.be/abcdefghijk'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_job_creation_and_listing_do_not_require_an_account(self):
        job = self.make_job()
        self.assertNotIn('owner_id', backend.JOBS[job['id']])
        self.assertEqual([j['id'] for j in self.client.get('/api/jobs').json()], [job['id']])
        self.assertEqual(self.client.get('/api/jobs/' + job['id']).status_code, 200)

    def test_login_registration_and_session_endpoints_are_removed(self):
        for path in ('register', 'login', 'logout'):
            response = self.client.post('/api/auth/' + path, json={'email': 'unused@example.com', 'password': 'unused-password'})
            self.assertIn(response.status_code, (404, 405))
        self.assertEqual(self.client.get('/api/auth/me').status_code, 404)
        self.assertFalse(any(path.startswith('/api/auth/') for path in self.client.get('/openapi.json').json()['paths']))

    def test_legacy_projects_share_the_library_without_exposing_owner_metadata(self):
        jobs = [self.make_job(), self.make_job()]
        for index, job in enumerate(jobs):
            raw = backend.JOBS[job['id']]
            raw.update(owner_id='former-owner-' + str(index))
            backend.persist_job(raw)
        backend.JOBS.clear()
        backend.load_persisted_jobs()
        response = self.client.get('/api/jobs', headers={'Authorization': 'Bearer obsolete-session'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({job['id'] for job in response.json()}, {job['id'] for job in jobs})
        self.assertNotIn('owner_id', response.text)

    def test_video_preview_and_subtitles_use_plain_backend_links(self):
        job = self.make_job()
        raw = backend.JOBS[job['id']]
        raw.update(status='completed', clips=[{'filename': 'cutflow-01.mp4', 'start': 60, 'end': 70}])
        folder = backend.OUTPUTS / job['id']
        folder.mkdir(parents=True)
        for filename, content in [('cutflow-01.mp4', b'video'), ('cutflow-01.preview.mp4', b'clean-preview'), ('cutflow-01.srt', b'1\n00:00:00,000 --> 00:00:01,000\nCaption\n')]:
            (folder / filename).write_bytes(content)
        clip = self.client.get('/api/jobs/' + job['id']).json()['clips'][0]
        self.assertNotIn('media_token', str(clip))
        self.assertEqual(self.client.get(clip['download_url']).content, b'video')
        self.assertEqual(self.client.get(clip['preview_url']).content, b'clean-preview')
        self.assertIn('Caption', self.client.get(clip['srt_url']).text)

    def test_cancel_retry_and_delete_do_not_require_an_account(self):
        job = self.make_job()
        base = '/api/jobs/' + job['id']
        self.assertEqual(self.client.post(base + '/cancel').json()['status'], 'cancelled')
        self.assertEqual(self.client.post(base + '/retry').status_code, 200)
        self.assertEqual(self.client.delete(base).json()['ok'], True)
        self.assertEqual(self.client.get(base).status_code, 404)

    def test_bulk_deletion_clears_the_shared_library_and_media(self):
        jobs = [self.make_job(), self.make_job()]
        for job in jobs:
            folder = backend.UPLOADS / job['id']
            folder.mkdir(parents=True)
            (folder / 'source.mp4').write_bytes(b'source')
        result = self.client.delete('/api/jobs')
        self.assertEqual(result.json(), {'ok': True, 'deleted_count': 2})
        self.assertEqual(self.client.get('/api/jobs').json(), [])
        self.assertFalse(any((backend.UPLOADS / j['id']).exists() for j in jobs))
        backend.JOBS.clear()
        backend.load_persisted_jobs()
        self.assertEqual(backend.JOBS, {})

    def test_global_job_capacity_remains_enforced(self):
        with patch.object(backend, 'MAX_ACTIVE_JOBS', 1):
            first = self.make_job()
            self.assertEqual(self.client.post('/api/jobs/url', json={'source_url': 'https://youtu.be/abcdefghijk'}).status_code, 429)
            backend.JOBS[first['id']]['status'] = 'completed'
            self.make_job()

    def test_cloud_cleanup_failures_are_reported_without_storage_locations(self):
        for bulk in (False, True):
            job = self.make_job()
            backend.JOBS[job['id']]['source_blob_url'] = 'https://private-storage.example/source'
            with patch.object(backend, 'blob_delete', return_value=False):
                response = self.client.delete('/api/jobs' if bulk else '/api/jobs/' + job['id'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['cloud_cleanup_failures'], 1)
            self.assertNotIn('private-storage', response.text)

    def test_invalid_upload_removes_unattached_cloud_source(self):
        cloud = {}
        def upload(path, remote_name):
            location = 'https://private-storage.example/' + remote_name
            cloud[location] = path.read_bytes()
            return location
        with patch.object(backend, 'blob_enabled', return_value=True), patch.object(backend, 'blob_upload', side_effect=upload), patch.object(backend, 'blob_delete', side_effect=lambda location: cloud.pop(location, None)):
            response = self.client.post('/api/jobs/upload', files={'file': ('video.mp4', b'source-video', 'video/mp4')}, data={'template': 'invalid-template'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(cloud, {})
        self.assertEqual(list(backend.UPLOADS.iterdir()), [])

    def test_running_cancelled_worker_exits_before_retry(self):
        started, release = threading.Event(), threading.Event()
        def work(job_id):
            started.set()
            release.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(backend, 'POOL', pool), patch.object(backend, 'process_job', side_effect=work):
            try:
                job = self.make_job()
                self.assertTrue(started.wait(2))
                base = '/api/jobs/' + job['id']
                self.client.post(base + '/cancel')
                self.assertEqual(self.client.post(base + '/retry').status_code, 409)
                release.set()
                pool.submit(lambda: None).result(5)
                self.assertEqual(self.client.post(base + '/retry').status_code, 200)
            finally:
                release.set()

    def test_cancelled_queued_worker_is_replaced_without_duplicate_processing(self):
        release = threading.Event()
        calls = []
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(backend, 'POOL', pool), patch.object(backend, 'process_job', side_effect=calls.append):
            blocker = pool.submit(release.wait, 5)
            try:
                job = self.make_job()
                base = '/api/jobs/' + job['id']
                self.client.post(base + '/cancel')
                self.assertEqual(self.client.post(base + '/retry').status_code, 200)
            finally:
                release.set()
                blocker.result(5)
                pool.shutdown(wait=True)
        self.assertEqual(calls, [job['id']])

    def test_configured_origin_receives_cors_without_authorization_header(self):
        response = self.client.options('/api/jobs/url', headers={'Origin': 'https://cutflow.example', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('access-control-allow-origin'), 'https://cutflow.example')
        self.assertEqual(self.client.get('/api/jobs', headers={'Origin': 'https://cutflow.example'}).status_code, 200)
        rejected = self.client.options('/api/jobs/url', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
        self.assertNotIn('access-control-allow-origin', rejected.headers)
