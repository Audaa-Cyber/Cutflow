"""Force temporary app storage before any test imports the application."""
import os
import tempfile
from pathlib import Path

_storage = None


def isolate_storage():
    global _storage
    if _storage is None:
        _storage = tempfile.TemporaryDirectory(prefix="cutflow-isolated-tests-")
    root = Path(_storage.name)
    os.environ["CUTFLOW_DATA_DIR"] = str(root)
    os.environ["CUTFLOW_DB_PATH"] = str(root / "cutflow.sqlite3")
    os.environ.setdefault("CUTFLOW_ALLOWED_ORIGINS", "https://cutflow.example")
    return root
