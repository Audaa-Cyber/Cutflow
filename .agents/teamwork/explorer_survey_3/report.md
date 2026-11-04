# Survey Report: Issue 3 — Project History Cleanup and Bulk Delete

## Executive Summary
This survey provides a comprehensive architectural and operational analysis for **Issue 3 (Project History Cleanup and Bulk Delete)** in Cutflow.
- **Current Data Footprint**: `data/cutflow.sqlite3` contains stale job records (initially 26 records, 37 after unmocked test runs) consuming ~176 KB. `data/uploads` holds 26 job folders totaling **1,126.97 MB**. `data/outputs` holds 25 job folders totaling **754.34 MB**. In total, **~1.88 GB** of obsolete video and audio artifacts are currently consuming disk space.
- **Missing Capabilities**: Cutflow currently supports single-job deletion via `DELETE /api/jobs/{job_id}`, but lacks a bulk deletion endpoint (`DELETE /api/jobs`) and a frontend "Delete all" button in the Projects view.
- **Scope of Changes**:
  1. Safe one-time purge of existing stale SQLite records and directory contents in `data/uploads` and `data/outputs`.
  2. Implement `DELETE /api/jobs` in `backend/app.py` to kill active child processes, mark jobs cancelled, clear in-memory `JOBS`, truncate SQLite table, and purge disk artifacts.
  3. Add a "Delete all" button in `frontend/index.html` projects view header toolbar.
  4. Style the button in `frontend/styles.css` with a danger palette matching existing cancel actions.
  5. Add `deleteAllProjects()` in `frontend/app.js` with native confirmation, API call, and complete UI reset (state, project counter, active processing, clips grid).
  6. Add unit test coverage for `delete_all_jobs` in `tests/test_cutflow.py`.

---

## 1. Current State Analysis

### 1.1 Database (`data/cutflow.sqlite3` & `data/cutflow.db`)
- **Active Database**: `data/cutflow.sqlite3`
  - Referenced in `backend/app.py`:
    ```python
    DB_PATH = Path(os.getenv("CUTFLOW_DB_PATH", str(DATA / "cutflow.sqlite3")))
    ```
  - Schema:
    ```sql
    CREATE TABLE jobs (
      id TEXT PRIMARY KEY,
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL,
      status TEXT NOT NULL,
      payload TEXT NOT NULL
    );
    ```
  - Status Breakdown of Stale Records:
    - `completed`: 18
    - `failed`: 15 (including test/stale runs)
    - `cancelled`: 4
  - Total records: 37
- **Legacy File**: `data/cutflow.db`
  - Contains 0 tables (empty SQLite file, 0 bytes). Not referenced anywhere in the repository. Safe to delete or leave empty.

### 1.2 Disk Artifacts (`data/uploads` & `data/outputs`)
- **`data/uploads`**:
  - Contains 26 subdirectories named after job UUIDs (e.g., `01cb7a6a6467495baa9a82b2bc002261/`, etc.).
  - Total size: **1,126.97 MB** (source video uploads, raw clips).
  - No loose files or non-directory files exist at the root level.
- **`data/outputs`**:
  - Contains 25 subdirectories named after job UUIDs.
  - Total size: **754.34 MB** (cut clips, rendered MP4s, subtitle SRT/ASS files, quality exports).
  - No loose files or non-directory files exist at the root level.
- **Total Disk Space to Reclaim**: **~1,881.31 MB (~1.88 GB)**.

### 1.3 Backend Architecture (`backend/app.py`)
- **In-Memory Tracking**:
  - `JOBS: dict[str, dict] = {}` (loaded on startup via `load_persisted_jobs()` from SQLite `jobs` table).
  - `LOCK = threading.RLock()`: Protects state mutations across concurrent worker threads.
- **Process & Cancellation Tracking**:
  - `CANCELLED_JOBS: set[str] = set()`
  - `ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}`
  - In `run_command()` (lines 289-313):
    ```python
    if job_id and (job_id in CANCELLED_JOBS or JOBS.get(job_id, {}).get("status") == "cancelled"):
        raise JobCancelledException("Processing was cancelled by user.")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if job_id:
        with LOCK:
            ACTIVE_PROCESSES[job_id] = process
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    ...
    ```
  - In `process_job()` (lines 1367-1528):
    - Periodically calls `check_cancelled()`, which raises `JobCancelledException` if `job_id in CANCELLED_JOBS`.
    - In `update_job()`:
      ```python
      def update_job(job_id: str, **updates) -> None:
          with LOCK:
              if job_id in JOBS:
                  JOBS[job_id].update(updates)
                  JOBS[job_id]["updated_at"] = time.time()
                  persist_job(JOBS[job_id])
      ```
      *Crucial Observation*: Because `update_job()` checks `if job_id in JOBS:`, if `JOBS.clear()` is called during bulk deletion, any remaining worker thread in `POOL` will NOT re-insert or resurrect deleted jobs into SQLite.
- **Existing Job Deletion Endpoint**:
  - `DELETE /api/jobs/{job_id}` (lines 1820-1840):
    ```python
    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise HTTPException(404, "Project not found.")
        CANCELLED_JOBS.add(job_id)
        proc = ACTIVE_PROCESSES.get(job_id)
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        with LOCK:
            job = JOBS.pop(job_id, None)
            with db_connection() as connection:
                connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        if not job:
            raise HTTPException(404, "Project not found.")
        for directory in (UPLOADS / job_id, OUTPUTS / job_id):
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)
        return {"ok": True}
    ```
  - There is currently **no** `@app.delete("/api/jobs")` bulk deletion endpoint.

### 1.4 Frontend Architecture (`frontend/index.html` & `frontend/app.js`)
- **Projects View in `frontend/index.html`** (lines 420-438):
  ```html
  <section class="view" id="projects-view">
    <div class="projects-heading">
      <div>
        <div class="eyebrow"><span class="eyebrow-line"></span> YOUR LIBRARY</div>
        <h1>Projects<span class="heading-period">.</span></h1>
        <p class="heading-copy">Every source and clip you've worked on in this session.</p>
      </div><button class="secondary-button" id="new-project-button">...</button>
    </div>
    ...
  </section>
  ```
- **Project Counter in Sidebar Navigation** (line 30):
  ```html
  <span class="nav-count" id="project-count">0</span>
  ```
- **State in `frontend/app.js`**:
  - `state.jobs = []`
  - `state.activeJobId = null`
  - `state.pollTimer = null`
  - Project count is updated via `$("#project-count").textContent = state.jobs.length;` inside `upsertJob()` and `deleteProject()`.
  - When `state.jobs` is empty, `renderProjects()` automatically displays the empty state:
    ```html
    <div class="empty-state">
      <div class="empty-symbol">...</div>
      <strong>Your library is waiting</strong>
      <p>Start with a video and your first clips will show up here.</p>
    </div>
    ```

---

## 2. Required Changes & Exact Specifications

### 2.1 Initial One-Time Stale Job & Artifact Cleanup
A safe cleanup script should purge the existing stale jobs from `data/cutflow.sqlite3` and empty `data/uploads` and `data/outputs` without deleting the root directories:
```python
import sqlite3, shutil
from pathlib import Path

# 1. Purge SQLite table
conn = sqlite3.connect("data/cutflow.sqlite3")
cur = conn.cursor()
cur.execute("DELETE FROM jobs")
conn.commit()
cur.execute("VACUUM")
conn.close()

# 2. Purge uploads and outputs directories
for target in [Path("data/uploads"), Path("data/outputs")]:
    if target.exists():
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
```

### 2.2 Backend Bulk Delete Endpoint (`backend/app.py`)
Insert `@app.delete("/api/jobs")` immediately above `@app.delete("/api/jobs/{job_id}")` (around line 1820).

```python
@app.delete("/api/jobs")
def delete_all_jobs():
    with LOCK:
        job_ids = list(JOBS.keys())
        all_ids = set(job_ids) | set(ACTIVE_PROCESSES.keys())
        for jid in all_ids:
            CANCELLED_JOBS.add(jid)
        for proc in list(ACTIVE_PROCESSES.values()):
            try:
                proc.kill()
            except Exception:
                pass
        ACTIVE_PROCESSES.clear()
        JOBS.clear()
        with db_connection() as connection:
            cursor = connection.execute("DELETE FROM jobs")
            deleted_count = cursor.rowcount
            if deleted_count < 0:
                deleted_count = len(job_ids)

    for directory in (UPLOADS, OUTPUTS):
        if directory.exists():
            for item in directory.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except Exception:
                    pass

    return {"ok": True, "deleted_count": deleted_count}
```
**Key Highlights**:
- Synchronously terminates all running subprocesses in `ACTIVE_PROCESSES`.
- Registers all active IDs in `CANCELLED_JOBS` so background threads immediately abort.
- Uses `LOCK` to avoid race conditions with incoming `create_job()` or `update_job()`.
- Uses `shutil.rmtree(..., ignore_errors=True)` and `item.unlink(missing_ok=True)` to prevent Windows file-lock crashes.
- Preserves the `UPLOADS` and `OUTPUTS` root directory folders.
- Returns `{"ok": True, "deleted_count": N}` adhering exactly to acceptance criteria.

### 2.3 Frontend HTML Layout (`frontend/index.html`)
In lines 421-427, add the "Delete all" button within a button group next to `new-project-button`:
```html
        <div class="projects-heading">
          <div>
            <div class="eyebrow"><span class="eyebrow-line"></span> YOUR LIBRARY</div>
            <h1>Projects<span class="heading-period">.</span></h1>
            <p class="heading-copy">Every source and clip you've worked on in this session.</p>
          </div>
          <div class="projects-heading-actions" style="display:flex;gap:8px;align-items:center;">
            <button class="secondary-button danger-button" id="delete-all-projects-button">
              Delete all
            </button>
            <button class="secondary-button" id="new-project-button"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:4px;" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>New project</button>
          </div>
        </div>
```

### 2.4 Frontend CSS Styling (`frontend/styles.css`)
Add explicit styling for danger buttons to ensure visually cohesive warning styling:
```css
.secondary-button.danger-button {
  border-color: #532929;
  background: #231717;
  color: #ff9e97;
}
.secondary-button.danger-button:hover {
  background: #351f1f;
  border-color: #7f3939;
  color: #ffb8b2;
}
```

### 2.5 Frontend JS Handlers (`frontend/app.js`)
1. Add `deleteAllProjects()`:
```javascript
async function deleteAllProjects() {
  if (!confirm("Are you sure you want to delete all projects and generated clips? This cannot be undone.")) return;
  try {
    const response = await fetch("/api/jobs", { method: "DELETE" });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!response.ok) {
      let msg = "Could not delete all projects.";
      if (isJson) {
        const err = await response.json().catch(() => ({}));
        msg = err.detail || msg;
      }
      throw new Error(msg);
    }
    const data = isJson ? await response.json() : {};
    state.jobs = [];
    state.activeJobId = null;
    clearTimeout(state.pollTimer);
    $("#active-processing").hidden = true;
    $("#latest-results").hidden = true;
    $("#project-count").textContent = "0";
    const button = $("#create-button");
    if (button) {
      button.disabled = false;
      $("#create-button-label").textContent = "Find my best clips";
    }
    renderProjects();
    showToast(`All projects deleted (${data.deleted_count ?? 0} removed).`);
  } catch (error) {
    showToast(error.message || "Failed to delete projects.");
  }
}
```
2. Attach event listener in `init()`:
```javascript
  const deleteAllBtn = $("#delete-all-projects-button");
  if (deleteAllBtn) {
    deleteAllBtn.addEventListener("click", deleteAllProjects);
  }
```

### 2.6 Unit Testing (`tests/test_cutflow.py`)
Add unit test:
```python
    def test_delete_all_jobs_clears_state_and_disk(self):
        from backend.app import JOBS, create_job, delete_all_jobs, db_connection
        job = create_job("podcast", "9:16", 2, 20, 45, source_path="dummy.mp4")
        self.assertIn(job["id"], JOBS)

        with db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM jobs WHERE id = ?", (job["id"],)).fetchone()[0]
            self.assertEqual(count, 1)

        result = delete_all_jobs()
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["deleted_count"], 1)
        self.assertEqual(len(JOBS), 0)

        with db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            self.assertEqual(count, 0)
```

---

## 3. Risk Assessment & Mitigations

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| Active FFmpeg or Whisper subprocess locked on Windows | File deletion fails with `PermissionError` | Subprocesses in `ACTIVE_PROCESSES` are killed first (`proc.kill()`). `shutil.rmtree(..., ignore_errors=True)` and `item.unlink(missing_ok=True)` gracefully handle any transient file locks. |
| In-flight worker thread wakes up and writes back to SQLite | Job resurrected after deletion | `update_job()` has a guard `if job_id in JOBS:`. Because `JOBS` is cleared, no post-deletion updates are persisted. `CANCELLED_JOBS` ensures workers terminate immediately. |
| User accidentally clicks "Delete all" | Irreversible loss of project history | Native browser `confirm()` modal prompts the user before sending the network request. |
| Deleting parent folders `data/uploads` or `data/outputs` | Subsequent upload/export fails with missing folder error | Deletion only clears `item` in `directory.iterdir()`; parent directories remain present. |
| SQLite `DELETE FROM jobs` rowcount return value | `cursor.rowcount` might return -1 or 0 in certain SQLite builds | Fallback to `len(job_ids)` if `cursor.rowcount < 0`. |

---

## 4. Verification Checklist

1. **Initial Cleanup Verification**:
   - `python -c "import sqlite3; conn = sqlite3.connect('data/cutflow.sqlite3'); print('Count:', conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])"` -> Returns `0`.
   - `python -c "from pathlib import Path; print('Uploads:', len(list(Path('data/uploads').iterdir())), 'Outputs:', len(list(Path('data/outputs').iterdir())))"` -> Returns `Uploads: 0 Outputs: 0`.
2. **API Endpoint Verification**:
   - `curl -X DELETE http://127.0.0.1:8000/api/jobs` -> Returns `{"ok": true, "deleted_count": N}`.
3. **Frontend UI Verification**:
   - Navigate to `http://127.0.0.1:8000/` and open "Projects" view.
   - Verify "Delete all" button renders with danger styling next to "New project".
   - Click "Delete all", dismiss the dialog -> No action taken.
   - Click "Delete all", confirm the dialog -> Toast notification displays, `#project-count` in navigation changes to `0`, projects list displays "Your library is waiting".
4. **Unit Test Verification**:
   - `.\.venv\Scripts\python.exe -m unittest discover tests/` passes.
