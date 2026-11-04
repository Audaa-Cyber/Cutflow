# Handoff Report: Survey Explorer 3 — Issue 3 (Project History Cleanup and Bulk Delete)

## 1. Observation
1. **Database inspection (`data/cutflow.sqlite3`)**:
   - Tool command: `python .agents/teamwork/explorer_survey_3/inspect_data.py`
   - Output:
     - SQLite Schema: `CREATE TABLE jobs (id TEXT PRIMARY KEY, created_at REAL NOT NULL, updated_at REAL NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL)`
     - 37 jobs total (26 original stale jobs + 11 test run artifacts): 18 completed, 15 failed, 4 cancelled.
     - `data/cutflow.db` is an unreferenced 0-byte SQLite database with 0 tables.
2. **Filesystem artifacts (`data/uploads` & `data/outputs`)**:
   - `data/uploads`: 26 subdirectories, 0 loose root files, total disk size: **1,126.97 MB**.
   - `data/outputs`: 25 subdirectories, 0 loose root files, total disk size: **754.34 MB**.
   - Total disk space to reclaim: **~1.88 GB**.
3. **Backend implementation (`backend/app.py`)**:
   - `JOBS: dict[str, dict] = {}` at line 203.
   - `LOCK = threading.RLock()` at line 204.
   - `CANCELLED_JOBS: set[str] = set()` at line 285.
   - `ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}` at line 286.
   - `run_command` at line 289 checks `if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"): raise JobCancelledException(...)`
   - `update_job` at line 272 checks `if job_id in JOBS:`.
   - Single-job delete endpoint exists at lines 1820-1840 (`@app.delete("/api/jobs/{job_id}")`).
   - Bulk delete endpoint `@app.delete("/api/jobs")` is missing.
4. **Frontend UI (`frontend/index.html` & `frontend/app.js`)**:
   - `frontend/index.html` line 30: `<span class="nav-count" id="project-count">0</span>`.
   - `frontend/index.html` lines 421-427 has `.projects-heading` with only `#new-project-button`; lacks a "Delete all" button.
   - `frontend/app.js` lines 467-482 has `deleteProject(id)` which prompts `confirm()`, deletes single job, updates `state.jobs`, `#project-count`, and calls `renderProjects()`.
   - `frontend/app.js` lacks `deleteAllProjects()` and listener for `#delete-all-projects-button`.
5. **Unit test suite (`tests/test_cutflow.py`)**:
   - Test command: `.\.venv\Scripts\python.exe -m unittest discover tests/`
   - Output: 31 tests ran, 5 failures (all due to Issue 2 `KeyError: 'base_color'`). No tests currently assert `delete_all_jobs` or bulk deletion.

## 2. Logic Chain
1. **Disk Reclaim Requirement**: Based on Observation 2, 26 upload directories and 25 output directories take up ~1.88 GB of storage. Purging these directories by iterating through `item in directory.iterdir()` safely removes all subdirectories without unlinking the parent `data/uploads` and `data/outputs` folders needed for future uploads.
2. **Database Cleanup Requirement**: Based on Observation 1, `jobs` table has 37 records. Executing `DELETE FROM jobs` empties the table and resets persisted job count to 0.
3. **Process Cancellation & Memory Safety**: Based on Observation 3, active background processes store handles in `ACTIVE_PROCESSES`, and background workers check `CANCELLED_JOBS`. By taking `LOCK`, adding all IDs to `CANCELLED_JOBS`, calling `proc.kill()` on all `ACTIVE_PROCESSES`, and clearing `JOBS`, running tasks will terminate immediately upon raising `JobCancelledException`.
4. **Resurrection Prevention**: Because `update_job()` in `backend/app.py` checks `if job_id in JOBS:`, calling `JOBS.clear()` guarantees that terminated worker threads cannot write back stale records into SQLite after the table is emptied.
5. **UI Consistency**: Based on Observation 4, adding `<button class="secondary-button danger-button" id="delete-all-projects-button">Delete all</button>` to `.projects-heading` in `frontend/index.html` and binding it in `frontend/app.js` to prompt `confirm()` and send `DELETE /api/jobs` allows users to purge all projects. Resetting `state.jobs = []`, `state.activeJobId = null`, and `$("#project-count").textContent = "0"` synchronizes the entire UI and renders the "Your library is waiting" empty state.

## 3. Caveats
- Windows file locking: If an active FFmpeg or Whisper process is killed asynchronously, file handles may briefly remain locked. The cleanup logic must use `shutil.rmtree(item, ignore_errors=True)` and `item.unlink(missing_ok=True)` to prevent 500 errors.
- Database location: Unit tests set `CUTFLOW_DB_PATH` in `tests/test_cutflow.py`, but tests that import `backend.app` outside that context or unmocked workers may write to `data/cutflow.sqlite3`. One-time initial cleanup must be executed before final verification.

## 4. Conclusion
Issue 3 is well-scoped and straightforward to resolve:
1. Run initial cleanup script to delete all rows from SQLite `jobs` in `data/cutflow.sqlite3` and purge contents of `data/uploads` and `data/outputs` (~1.88 GB reclaimed).
2. Implement `@app.delete("/api/jobs")` in `backend/app.py` directly before `@app.delete("/api/jobs/{job_id}")`.
3. Add `<button class="secondary-button danger-button" id="delete-all-projects-button">Delete all</button>` to `frontend/index.html`.
4. Add danger button CSS styles in `frontend/styles.css`.
5. Add `deleteAllProjects()` handler and event listener in `frontend/app.js`.
6. Add unit test `test_delete_all_jobs_clears_state_and_disk` to `tests/test_cutflow.py`.

## 5. Verification Method
1. **Initial Cleanup Verification**:
   ```powershell
   .\.venv\Scripts\python.exe -c "import sqlite3; conn = sqlite3.connect('data/cutflow.sqlite3'); print('Count:', conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])"
   ```
   *Expected output*: `Count: 0`.
   ```powershell
   .\.venv\Scripts\python.exe -c "from pathlib import Path; print('Uploads:', len(list(Path('data/uploads').iterdir())), 'Outputs:', len(list(Path('data/outputs').iterdir())))"
   ```
   *Expected output*: `Uploads: 0 Outputs: 0`.
2. **Unit Test Verification**:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover tests/
   ```
   *Expected output*: All unit tests pass (including new `test_delete_all_jobs_clears_state_and_disk` once Issue 2 fix is also applied).
3. **API Endpoint Verification**:
   - Send `DELETE http://127.0.0.1:8000/api/jobs`.
   - Verify HTTP 200 response with payload `{"ok": true, "deleted_count": N}`.
4. **UI Verification**:
   - Open Cutflow web app -> Projects tab.
   - Click "Delete all" -> Verify confirmation dialog appears.
   - Confirm dialog -> Verify list displays empty state, navigation counter resets to 0, and toast shows success.
