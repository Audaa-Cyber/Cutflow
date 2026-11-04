# Dispatch: Worker M3 (Project History Cleanup and Bulk Delete)

## Role
Implementation Worker for Milestone 3 (Project History Cleanup and Bulk Delete Endpoint + UI)

## Working Directory
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_m3

## Task
Read ORIGINAL_REQUEST.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md`

Read PROJECT.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md`

Read Survey Explorer 3 report at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_3\report.md`

## Write Ownership
You exclusively own:
- `data/cutflow.sqlite3`, `data/uploads/`, `data/outputs/` (perform the one-time cleanup)
- `backend/app.py` (add `DELETE /api/jobs` endpoint around line 1820)
- `frontend/index.html` (lines 420-435: add "Delete all" button in projects view)
- `frontend/styles.css` (add `.secondary-button.danger-button` styles)
- `frontend/app.js` (add `deleteAllProjects()` and attach event listener)

## Detailed Requirements
1. **Initial Cleanup**:
   - Safely purge all rows from `jobs` table in `data/cutflow.sqlite3` and VACUUM.
   - Remove all contents inside `data/uploads` and `data/outputs` without deleting the root directories.
2. **Backend `DELETE /api/jobs` Endpoint (`backend/app.py`)**:
   - Implement `@app.delete("/api/jobs")`:
     - Kills all processes in `ACTIVE_PROCESSES`.
     - Adds all job IDs to `CANCELLED_JOBS`.
     - Clears `ACTIVE_PROCESSES` and `JOBS`.
     - Deletes all records from SQLite `jobs` table via `db_connection()`.
     - Purges all subdirectories and files in `UPLOADS` and `OUTPUTS`.
     - Returns `{"ok": True, "deleted_count": deleted_count}`.
3. **Frontend Layout (`frontend/index.html`)**:
   - Add `<button class="secondary-button danger-button" id="delete-all-projects-button">Delete all</button>` in the projects heading actions next to `new-project-button`.
4. **Frontend Styles (`frontend/styles.css`)**:
   - Add `.secondary-button.danger-button` styling.
5. **Frontend Handler (`frontend/app.js`)**:
   - Add `async function deleteAllProjects()` with `confirm()` dialog.
   - Issue `fetch("/api/jobs", { method: "DELETE" })`.
   - On success: clear `state.jobs = []`, `state.activeJobId = null`, reset `#project-count` to `0`, hide `#active-processing` and `#latest-results`, reset `#create-button`, call `renderProjects()`, and `showToast()`.
   - Attach click listener to `#delete-all-projects-button` in `init()`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
Run tests:
`.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1BulkJobDeletion tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_with_zero_jobs_returns_cleanly tests.test_e2e_features.TestTier2BoundaryAndCornerCases.test_bulk_delete_handles_missing_or_empty_disk_dirs`
Run full discover:
`.\.venv\Scripts\python.exe -m unittest discover tests/`
Document commands and results in your handoff report.
Write `handoff.md` and send a message when finished.
