import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkerRuntimeTests(unittest.TestCase):
    def test_one_configured_worker_never_starts_second_job_until_first_finishes(self):
        with tempfile.TemporaryDirectory(prefix="cutflow-worker-test-") as directory:
            environment = dict(os.environ, CUTFLOW_DATA_DIR=directory,
                               CUTFLOW_DB_PATH=str(Path(directory) / "jobs.sqlite3"), WORKER_CONCURRENCY="1")
            code = """
import json, threading
from backend.app import POOL
first = threading.Event()
second = threading.Event()
release = threading.Event()
def work(marker):
    marker.set()
    release.wait(2)
one = POOL.submit(work, first)
first.wait(1)
two = POOL.submit(work, second)
started_early = second.wait(0.2)
release.set()
one.result(3)
two.result(3)
print(json.dumps({'second_started_early': started_early, 'second_finished': second.is_set()}))
POOL.shutdown()
"""
            result = subprocess.run([sys.executable, "-c", code], env=environment,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertFalse(state["second_started_early"])
            self.assertTrue(state["second_finished"])
