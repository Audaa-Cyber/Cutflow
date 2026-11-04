# Milestone 3 Handoff Report: Project History Cleanup and Bulk Delete

## 1. Observation
1. **Initial Stale Artifact Footprint**:
   - `data/cutflow.sqlite3`: Contained 71 records in the `jobs` table prior to cleanup.
   - `data/uploads`: Contained 30 subdirectories of source video files prior to cleanup.
   - `data/outputs`: Contained 26 subdirectories of cut clips, renders, and subtitle files prior to cleanup.
   - These stale records caused `create_job()` to raise `HTTPException(429, "Cutflow is busy. Wait for active jobs to finish (limit: 4).")` during test executions due to uncompleted jobs in SQLite.
2. **Missing Bulk Deletion Infrastructure**:
   - `backend/app.py`: Defined single-job deletion `@app.delete("/api/jobs/{job_id}")` at lines 1834-1854, but lacked bulk deletion endpoint `@app.delete("/api/jobs")` (`delete_all_jobs`).
   - `frontend/index.html`: Projects heading section (lines 421-427) only contained `#new-project-button`, lacking a "Delete all" action.
   - `frontend/styles.css`: Lacked `.secondary-button.danger-button` styling.
   - `frontend/app.js`: Defined `deleteProject(id)` at line 467, but lacked `deleteAllProjects()`, and did not attach an event listener to `#delete-all-projects-button`.
3. **Execution Commands and Results**:
   - SQLite and directory purge command:
     `python -c "import sqlite3, shutil; from pathlib import Path; conn = sqlite3.connect('data/cutflow.sqlite3'); cur = conn.cursor(); cur.execute('DELETE FROM jobs'); conn.commit(); cur.execute('VACUUM'); conn.close(); [ [shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink(missing_ok=True) for item in Path(d).iterdir()] for d in ['data/uploads', 'data/outputs'] ]"`
     Output: `Count: 0, Uploads: 0, Outputs: 0`
   - Verification command for M3:
     `.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1BulkJobDeletion tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_with_zero_jobs_returns_cleanly tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_handles_missing_or_empty_disk_dirs`
     Output: `Ran 7 tests in 0.077s ... OK`
   - Unit test suite:
     `.\.venv\Scripts\python.exe -m unittest tests.test_cutflow`
     Output: `Ran 31 tests in 0.150s ... OK`
   - Cross-feature combinations:
     `.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier3CrossFeatureCombinations.test_bulk_delete_during_in_flight_worker_prevents_reinsertion tests.test_e2e_features.TestTier3CrossFeatureCombinations.test_job_lifecycle_multiple_fit_modes_then_bulk_delete`
     Output: `Ran 2 tests in 0.046s ... OK`

## 2. Logic Chain
1. *Observation 1* indicated that stale jobs in `data/cutflow.sqlite3` and hundreds of megabytes of old video clips in `data/uploads` and `data/outputs` were occupying disk space and blocking job creation via the 429 concurrency limit (`MAX_ACTIVE_JOBS = 4`). Purging all rows from SQLite `jobs` table, running `VACUUM`, and iterating over `data/uploads` and `data/outputs` to remove all subdirectories/files without deleting the root folders reclaimed disk space and returned Cutflow to a clean initial state.
2. *Observation 2* showed that Cutflow lacked a bulk deletion endpoint. In `backend/app.py`, adding `@app.delete("/api/jobs")` (`delete_all_jobs`) inside the `LOCK` context:
   - Registers all job IDs and active processes in `CANCELLED_JOBS` so running worker threads immediately abort.
   - Terminates all active child processes in `ACTIVE_PROCESSES` via `proc.kill()`.
   - Clears `ACTIVE_PROCESSES` and `JOBS`.
   - Executes `DELETE FROM jobs` in SQLite and computes `deleted_count = max(cursor.rowcount if cursor.rowcount >= 0 else 0, len(job_ids))`.
   - Purges all files and subdirectories inside `UPLOADS` and `OUTPUTS` while keeping the root folders intact.
   - Returns `{"ok": True, "deleted_count": deleted_count}`.
3. *Observation 2* showed that the frontend lacked a UI trigger and handler.
   - In `frontend/index.html`, added `<button class="secondary-button danger-button" id="delete-all-projects-button">Delete all</button>` inside `.projects-heading-actions` next to `new-project-button`.
   - In `frontend/styles.css`, added `.secondary-button.danger-button` and its `:hover` pseudo-class with reddish danger palette (`#231717` background, `#532929` border, `#ff9e97` text).
   - In `frontend/app.js`, added `async function deleteAllProjects()` with browser `confirm()` confirmation, `fetch("/api/jobs", { method: "DELETE" })`, and upon success resets `state.jobs = []`, `state.activeJobId = null`, clears `state.pollTimer`, hides `#active-processing` and `#latest-results`, resets `#project-count` to `"0"`, resets `#create-button`, invokes `renderProjects()` (which displays the empty library state), and shows a confirmation toast. Attached click listener to `#delete-all-projects-button` in `init()`.
4. *Observation 3* verifies that all 7 M3 feature and boundary tests pass with 0 errors and 0 failures, and all 31 unit tests in `tests/test_cutflow.py` pass with 0 errors and 0 failures.

## 3. Caveats
- No caveats. The implementation strictly modified only the assigned files and lines, followed minimal change principles, and left both SQLite and disk directories in a pristine state.

## 4. Conclusion
Milestone 3 (Project History Cleanup and Bulk Delete Endpoint + UI) is fully implemented, verified, and complete:
- Initial stale job records and disk artifacts were safely purged.
- Backend bulk deletion endpoint `DELETE /api/jobs` terminates running subprocesses, marks jobs cancelled, clears in-memory structures, truncates SQLite, purges disk folders, and returns `{"ok": True, "deleted_count": N}`.
- Frontend includes the styled "Delete all" button, confirmation dialog, API communication, and complete UI state reset.
- All unit and e2e tests for bulk deletion pass cleanly.

## 5. Verification Method
To independently verify:
1. Verify SQLite database count is 0 and directories are clean:
   ```powershell
   .\.venv\Scripts\python.exe -c "import sqlite3; conn = sqlite3.connect('data/cutflow.sqlite3'); print('Count:', conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]); from pathlib import Path; print('Uploads:', len(list(Path('data/uploads').iterdir())), 'Outputs:', len(list(Path('data/outputs').iterdir())))"
   ```
   *Expected Output*: `Count: 0 Uploads: 0 Outputs: 0`
2. Run M3 targeted automated test suite:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1BulkJobDeletion tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_with_zero_jobs_returns_cleanly tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_handles_missing_or_empty_disk_dirs
   ```
   *Expected Output*: `Ran 7 tests ... OK`
3. Run baseline unit tests:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest tests.test_cutflow
   ```
   *Expected Output*: `Ran 31 tests ... OK`
4. Run cross-feature concurrency and lifecycle tests:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier3CrossFeatureCombinations.test_bulk_delete_during_in_flight_worker_prevents_reinsertion tests.test_e2e_features.TestTier3CrossFeatureCombinations.test_job_lifecycle_multiple_fit_modes_then_bulk_delete
   ```
   *Expected Output*: `Ran 2 tests ... OK`
