"""HTTP regressions for persistent accounts and private project access."""
import hashlib
import importlib
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tests._isolation import isolate_storage
from unittest.mock import patch

os.environ.setdefault("CUTFLOW_ALLOWED_ORIGINS", "https://cutflow.example")
isolate_storage()
from starlette.testclient import TestClient
import backend.app as backend


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cutflow-auth-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in {"DB_PATH": root / "db.sqlite3", "UPLOADS": root / "uploads", "OUTPUTS": root / "outputs"}.items():
            p = patch.object(backend, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.saved_jobs = backend.JOBS.copy()
        backend.JOBS.clear()
        self.addCleanup(self.restore_jobs)
        saved_futures = backend.WORKER_FUTURES.copy()
        backend.WORKER_FUTURES.clear()
        def restore_futures():
            backend.WORKER_FUTURES.clear()
            backend.WORKER_FUTURES.update(saved_futures)
        self.addCleanup(restore_futures)
        backend.load_persisted_jobs()
        pool = patch.object(backend.POOL, "submit")
        pool.start()
        self.addCleanup(pool.stop)
        self.client = TestClient(backend.app)
        self.addCleanup(self.client.close)

    def restore_jobs(self):
        backend.JOBS.clear()
        backend.JOBS.update(self.saved_jobs)

    def register(self, email="alice@example.com"):
        response = self.client.post("/api/auth/register", json={"email": email, "password": "correct horse battery"})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        return data, {"Authorization": "Bearer " + data["token"]}

    def make_job(self, headers):
        response = self.client.post("/api/jobs/url", headers=headers, json={"source_url": "https://youtu.be/abcdefghijk"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_accounts_persist_and_passwords_and_sessions_are_not_stored_in_plaintext(self):
        data, headers = self.register(" ALICE@EXAMPLE.COM ")
        self.assertEqual(data["user"]["email"], "alice@example.com")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json(), {"user": data["user"]})
        login = self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"})
        self.assertEqual(login.status_code, 200)
        self.assertNotEqual(login.json()["token"], data["token"])
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong password"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "alice@example.com", "password": "correct horse battery"}).status_code, 409)
        with backend.db_connection() as db:
            dump = " ".join(db.iterdump())
        self.assertNotIn("correct horse battery", dump)
        self.assertNotIn(data["token"], dump)
        # Reconstructing the store must retain accounts and existing sessions.
        auth = importlib.import_module("backend.auth")
        restored = auth.AuthStore(lambda: backend.DB_PATH)
        self.assertEqual(restored.authenticate(data["token"])["user"], data["user"])

    def test_logout_and_expired_bearer_tokens_are_rejected(self):
        data, headers = self.register()
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/jobs", headers=headers).status_code, 401)
        login = self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"}).json()
        with backend.db_connection() as db:
            db.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?", (time.time() - 1, hashlib.sha256(login["token"].encode()).hexdigest()))
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login["token"]}).status_code, 401)

    def test_all_job_routes_require_authentication_and_legacy_jobs_remain_private(self):
        for method, url in [("get", "/api/jobs"), ("post", "/api/jobs/url"), ("post", "/api/jobs/upload"), ("delete", "/api/jobs")]:
            self.assertEqual(getattr(self.client, method)(url).status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        _, headers = self.register()
        with patch.object(backend.POOL, "submit"):
            legacy = backend.create_job("podcast", "9:16", 1, 10, 20, source_path="private.mp4")
        self.assertEqual(self.client.get("/api/jobs", headers=headers).json(), [])
        self.assertEqual(self.client.get("/api/jobs/" + legacy["id"], headers=headers).status_code, 404)

    def test_second_account_cannot_read_or_mutate_first_account_jobs(self):
        _, alice = self.register()
        job = self.make_job(alice)
        _, bob = self.register("bob@example.com")
        prefix = "/api/jobs/" + job["id"]
        self.assertEqual(self.client.get("/api/jobs", headers=bob).json(), [])
        for method, suffix in [("get", ""), ("get", "/candidates"), ("get", "/clips/cutflow-01.mp4/timeline"), ("get", "/clips/cutflow-01.mp4"), ("get", "/clips/cutflow-01.mp4/preview"), ("post", "/clips/cutflow-01.mp4/export"), ("post", "/cancel"), ("post", "/retry"), ("delete", "")]:
            self.assertEqual(getattr(self.client, method)(prefix + suffix, headers=bob).status_code, 404, suffix)
        self.assertEqual(self.client.get(prefix, headers=alice).status_code, 200)

    def test_media_grants_are_scoped_expire_and_revoke_without_leaking_storage_urls(self):
        _, headers = self.register()
        job = self.make_job(headers)
        folder = backend.OUTPUTS / job["id"]
        folder.mkdir(parents=True)
        (folder / "cutflow-01.mp4").write_bytes(b"private-video")
        raw = backend.JOBS[job["id"]]
        raw.update(source_blob_url="https://private.blob.vercel-storage.com/source", clips=[{"filename": "cutflow-01.mp4", "start": 60, "end": 70, "download_url": "https://private.blob.vercel-storage.com/clip", "artifacts": {"mp4": "https://private.blob.vercel-storage.com/clip"}}])
        public = self.client.get("/api/jobs/" + job["id"], headers=headers).json()
        self.assertNotIn("blob.vercel-storage.com", str(public))
        self.assertNotIn("source_url", public)
        media_url = public["clips"][0]["download_url"]
        self.assertIn("media_token=", media_url)
        self.assertEqual(self.client.get(media_url).content, b"private-video")
        self.assertNotIn("media_token=", raw["clips"][0]["download_url"])
        token = media_url.split("media_token=", 1)[1]
        prefix = "/api/jobs/" + job["id"]
        self.assertEqual(self.client.get(prefix + "?media_token=" + token).status_code, 401)
        self.assertEqual(self.client.get(prefix + "/clips/cutflow-02.mp4?media_token=" + token).status_code, 401)
        with patch("backend.auth.time.time", return_value=time.time() + 1000):
            self.assertEqual(self.client.get(media_url).status_code, 401)
        self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(self.client.get(media_url).status_code, 401)

    def test_bulk_delete_only_removes_owner_jobs_and_media(self):
        _, alice = self.register()
        a = self.make_job(alice)
        _, bob = self.register("bob@example.com")
        b = self.make_job(bob)
        for job in [a, b]:
            folder = backend.UPLOADS / job["id"]
            folder.mkdir(parents=True)
            (folder / "source.mp4").write_bytes(b"keep owner media")
        result = self.client.delete("/api/jobs", headers=alice)
        self.assertEqual(result.json(), {"ok": True, "deleted_count": 1})
        self.assertFalse((backend.UPLOADS / a["id"]).exists())
        self.assertTrue((backend.UPLOADS / b["id"] / "source.mp4").exists())
        self.assertEqual(self.client.get("/api/jobs/" + b["id"], headers=bob).status_code, 200)
        backend.JOBS.clear()
        backend.load_persisted_jobs()
        self.assertEqual(set(backend.JOBS), {b["id"]})

    def test_owner_quota_prevents_one_owner_from_filling_queue(self):
        _, alice = self.register()
        with patch.object(backend, "MAX_OWNER_ACTIVE_JOBS", 1), patch.object(backend, "MAX_OWNER_JOBS", 2):
            a = self.make_job(alice)
            self.assertEqual(self.client.post("/api/jobs/url", headers=alice, json={"source_url": "https://youtu.be/abcdefghijk"}).status_code, 429)
            backend.JOBS[a["id"]]["status"] = "completed"
            b = self.make_job(alice)
            backend.JOBS[b["id"]]["status"] = "completed"
            self.assertEqual(self.client.post("/api/jobs/url", headers=alice, json={"source_url": "https://youtu.be/abcdefghijk"}).status_code, 429)
        _, bob = self.register("bob@example.com")
        self.make_job(bob)

    def test_single_deletion_reports_failed_cloud_cleanup_without_storage_locations(self):
        _, headers = self.register()
        job = self.make_job(headers)
        private_location = 'https://private-storage.example/private-source'
        backend.JOBS[job['id']]['source_blob_url'] = private_location
        with patch.object(backend, 'blob_delete', return_value=False):
            response = self.client.delete('/api/jobs/' + job['id'], headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('cloud_cleanup_failures'), 1)
        self.assertNotIn(private_location, response.text)
        self.assertEqual(self.client.get('/api/jobs/' + job['id'], headers=headers).status_code, 404)

    def test_bulk_deletion_reports_cloud_cleanup_failures_only_for_current_owner(self):
        _, alice = self.register()
        a = self.make_job(alice)
        _, bob = self.register('bob@example.com')
        b = self.make_job(bob)
        backend.JOBS[a['id']]['source_blob_url'] = 'https://private-storage.example/alice-source'
        backend.JOBS[b['id']]['source_blob_url'] = 'https://private-storage.example/bob-source'
        with patch.object(backend, 'blob_delete', return_value=False):
            response = self.client.delete('/api/jobs', headers=alice)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('cloud_cleanup_failures'), 1)
        self.assertEqual(response.json()['deleted_count'], 1)
        self.assertEqual(self.client.get('/api/jobs/' + b['id'], headers=bob).status_code, 200)
        self.assertNotIn('private-storage', response.text)

    def test_retry_cannot_submit_duplicate_worker_for_an_active_job(self):
        _, headers = self.register()
        job = self.make_job(headers)
        response = self.client.post("/api/jobs/" + job["id"] + "/retry", headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(backend.JOBS[job["id"]]["status"], "queued")

    def test_running_cancelled_worker_must_exit_before_retry(self):
        _, headers = self.register()
        started, release = threading.Event(), threading.Event()
        def work(job_id):
            started.set()
            release.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(backend, 'POOL', pool), patch.object(backend, 'process_job', side_effect=work):
            try:
                job = self.make_job(headers)
                self.assertTrue(started.wait(2))
                self.client.post('/api/jobs/' + job['id'] + '/cancel', headers=headers)
                response = self.client.post('/api/jobs/' + job['id'] + '/retry', headers=headers)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(backend.JOBS[job['id']]['status'], 'cancelled')
                release.set()
                pool.submit(lambda: None).result(5)
                self.assertEqual(self.client.post('/api/jobs/' + job['id'] + '/retry', headers=headers).status_code, 200)
            finally:
                release.set()

    def test_cancelled_queued_worker_is_removed_before_retry_is_queued(self):
        _, headers = self.register()
        release = threading.Event()
        calls = []
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(backend, 'POOL', pool), patch.object(backend, 'process_job', side_effect=calls.append):
            blocker = pool.submit(release.wait, 5)
            try:
                job = self.make_job(headers)
                self.client.post('/api/jobs/' + job['id'] + '/cancel', headers=headers)
                response = self.client.post('/api/jobs/' + job['id'] + '/retry', headers=headers)
                self.assertEqual(response.status_code, 200)
            finally:
                release.set()
                blocker.result(5)
                pool.shutdown(wait=True)
        self.assertEqual(calls, [job['id']], 'the cancelled callback must not run alongside the retry')

    def test_auth_attempt_window_is_bounded_persistent_and_recovers_after_expiry(self):
        with patch.dict(os.environ, {"CUTFLOW_AUTH_MAX_ATTEMPTS": "3", "CUTFLOW_AUTH_RATE_WINDOW_SECONDS": "60"}):
            self.register()
            for _ in range(2):
                self.assertEqual(self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong password"}).status_code, 401)
            blocked = self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"})
            self.assertEqual(blocked.status_code, 429)
            self.assertIn("Retry-After", blocked.headers)
            auth = importlib.import_module("backend.auth")
            with patch.object(backend, "AUTH_STORE", auth.AuthStore(lambda: backend.DB_PATH)):
                self.assertEqual(self.client.post("/api/auth/register", json={"email": "bob@example.com", "password": "correct horse battery"}).status_code, 429)
            with patch("backend.auth.time.time", return_value=time.time() + 61):
                self.assertEqual(self.client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"}).status_code, 200)

    def test_direct_login_rejects_oversized_password_before_hashing(self):
        self.register()
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            backend.AUTH_STORE.login("alice@example.com", "x" * 1025)
        self.assertEqual(error.exception.status_code, 400)

    def test_invalid_uploaded_job_removes_its_private_cloud_source(self):
        _, headers = self.register()
        cloud = {}
        def upload(path, remote_name):
            location = "https://private-storage.example/" + remote_name
            cloud[location] = path.read_bytes()
            return location
        with patch.object(backend, "blob_enabled", return_value=True), patch.object(backend, "blob_upload", side_effect=upload), patch.object(backend, "blob_delete", side_effect=lambda location: cloud.pop(location, None)):
            response = self.client.post("/api/jobs/upload", headers=headers, files={"file": ("video.mp4", b"source video", "video/mp4")}, data={"template": "invalid-template"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(cloud, {})
        self.assertEqual(list(backend.UPLOADS.iterdir()), [])

    def test_configured_origin_receives_cors_for_auth_and_auth_errors(self):
        response = self.client.options("/api/jobs", headers={"Origin": "https://cutflow.example", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "https://cutflow.example")
        self.assertEqual(self.client.get("/api/jobs", headers={"Origin": "https://cutflow.example"}).headers.get("access-control-allow-origin"), "https://cutflow.example")
        rejected = self.client.options("/api/jobs", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"})
        self.assertNotIn("access-control-allow-origin", rejected.headers)


if __name__ == "__main__":
    unittest.main()
