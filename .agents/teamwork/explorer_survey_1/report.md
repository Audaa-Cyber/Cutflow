# Investigation Report: Issue 1 – Default Canvas Framing in Aspect Conversion and Evo Flow

**Survey Explorer:** Survey Explorer 1  
**Target:** Cutflow MVP  
**Scope:** Issue 1 (Default Canvas Framing in Aspect Conversion and Evo Flow: `frontend/index.html`, `frontend/app.js`, and backend impact in `backend/app.py`)  
**Date:** 2026-10-30T21:18:00Z  

---

## 1. Executive Summary

This investigation surveys the current implementation of **Canvas Framing (Ambient Blur)** across the frontend UI, client-side state machine, Evo preset integration, and backend video rendering pipeline.

### Core Findings:
1. **Frontend HTML (`frontend/index.html`)**:
   - The framing mode radio button group exists at lines 197–216 with 3 options (`blur`, `letterbox`, `crop`).
   - The first button (`data-fit-mode="blur"`) already possesses the `selected` class, but its text is currently labeled simply `Ambient Blur`.
   - Button 2 is labeled `Black Bars (No Blur)` and Button 3 is labeled `Smart Crop (Full Fill)`.
   - To satisfy Requirement R1 and match the user-facing specifications in the implementation plan, the button text strings should be updated to:
     - Button 1: **`Canvas Framing (Ambient Blur)`** (remains `selected`)
     - Button 2: **`Black Bars (Letterbox)`**
     - Button 3: **`Smart Crop (Center Punch-in)`**
   - Accessibility can be improved by adding `role="radio"` and `aria-checked="true|false"` to the buttons within the existing `role="radiogroup"`.

2. **Frontend State & Event Flow (`frontend/app.js`)**:
   - `state.fitMode` is initialized to `"blur"` at line 4 (`fitMode: "blur"`).
   - `readSettings()` at line 92 correctly reads `fit_mode: state.fitMode || "blur"`.
   - Event listener at lines 521–524 captures clicks on `.fit-mode-btn` and updates `state.fitMode = button.dataset.fitMode`.
   - The Evo preset flow (clicking the Evo caption card in the flagship grid, the modal explorer, or using the "Evo Frosted Pill" prompt chip) sets `state.captionStyle = "evo"` without altering `state.fitMode`, thus naturally inheriting the default `"blur"` fit mode.
   - When a job is submitted via `createProject()`, `fit_mode: "blur"` is serialized into either `FormData` (upload) or JSON (URL).

3. **Backend Video Rendering Pipeline (`backend/app.py`)**:
   - Pydantic models (`JobPayload` line 269) and FastAPI route handlers (`upload_job` line 1622, `create_job` line 1547) default `fit_mode` to `"blur"`.
   - `process_job()` retrieves `fit_mode = job.get("fit_mode", "blur")` at line 1465 and passes it to `render_clip()`.
   - In `render_clip()`, line 1259 has default argument `fit_mode: str = "fit"`. While lines 1297–1306 treat any mismatch not equal to `"crop"` as ambient blur (`boxblur=28:5`), setting the default argument in `render_clip()` explicitly to `fit_mode: str = "blur"` ensures complete architectural consistency.
   - All 3 framing options (`letterbox`, `crop`, `blur`) are already covered by unit tests in `tests/test_cutflow.py:351` (`test_fit_mode_framing_options_in_render_clip`) and pass.

---

## 2. Requirement Checklist & Current Status

| Requirement / Acceptance Item | Location | Current State | Required Modification |
|---|---|---|---|
| 'Canvas Framing (Ambient Blur)' is pre-selected by default in the frontend Aspect Conversion / Smart Crop selector | `frontend/index.html:203-215` | Pre-selected class `selected` exists on `data-fit-mode="blur"`, but text is `Ambient Blur` | Update button text to `Canvas Framing (Ambient Blur)` and keep `selected` class |
| Button 2 & 3 labeled per specification | `frontend/index.html:207-214` | Labeled `Black Bars (No Blur)` and `Smart Crop (Full Fill)` | Update to `Black Bars (Letterbox)` and `Smart Crop (Center Punch-in)` |
| `state.fitMode` defaults to `"blur"` | `frontend/app.js:4` | Initialized to `"blur"` | Already compliant |
| `readSettings()` outputs `fit_mode: "blur"` | `frontend/app.js:92` | Uses `state.fitMode || "blur"` | Already compliant |
| Evo preset flow preserves `fit_mode: "blur"` | `frontend/app.js:560-580`, `index.html:266` | Selecting Evo does not overwrite `state.fitMode` | Already compliant |
| Backend defaults `fit_mode` to `"blur"` | `backend/app.py:269, 1465, 1547, 1622` | Defaults to `"blur"` in schema and routes; `render_clip` signature defaults to `"fit"` | Change line 1259 `render_clip` default parameter from `"fit"` to `"blur"` |

---

## 3. Deep Dive: Codebase Anatomy

### 3.1 `frontend/index.html` (Lines 197–216)

```html
197:             <div class="setting-group">
198:               <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
199:                 <label style="margin:0;">Canvas framing &amp; blur</label>
200:                 <span class="caption-sublabel-meta">ASPECT CONVERSION</span>
201:               </div>
202:               <div class="fit-mode-options" role="radiogroup" aria-label="Canvas framing mode">
203:                 <button type="button" class="fit-mode-btn selected" data-fit-mode="blur">
204:                   <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 12a4 4 0 0 0 8 0"/></svg>
205:                   <span>Ambient Blur</span>
206:                 </button>
207:                 <button type="button" class="fit-mode-btn" data-fit-mode="letterbox">
208:                   <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="8" x2="21" y2="8"/><line x1="3" y1="16" x2="21" y2="16"/></svg>
209:                   <span>Black Bars (No Blur)</span>
210:                 </button>
211:                 <button type="button" class="fit-mode-btn" data-fit-mode="crop">
212:                   <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>
213:                   <span>Smart Crop (Full Fill)</span>
214:                 </button>
215:               </div>
216:             </div>
```

**Observation:**
- Container: `.fit-mode-options` with `role="radiogroup"`.
- Buttons have class `.fit-mode-btn` and attribute `data-fit-mode`.
- Button 1 is marked `selected`.
- CSS styling in `frontend/styles.css:161-166`:
  ```css
  .fit-mode-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 6px; }
  .fit-mode-btn { background: #131510; border: 1px solid #282f1f; border-radius: 8px; padding: 9px 10px; font-size: 11px; font-weight: 600; color: #9da493; cursor: pointer; transition: all .18s ease; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; text-align: center; }
  .fit-mode-btn.selected { background: #232b1a; border-color: var(--lime); color: var(--lime); box-shadow: 0 0 12px rgba(213,255,95,.18); }
  ```
- The grid column width comfortably accommodates the new label `Canvas Framing (Ambient Blur)` with natural multi-line wrapping in standard display viewports.

### 3.2 `frontend/app.js` (Relevant Sections)

1. **State Declaration (Lines 1–18):**
   ```javascript
   const state = {
     template: "podcast",
     aspectRatio: "9:16",
     fitMode: "blur", // Line 4: Correctly initialized to "blur"
     captionStyle: "focus",
     ...
   };
   ```

2. **Reading Settings for API Dispatch (Lines 78–105):**
   ```javascript
   function readSettings() {
     ...
     return {
       template: state.template,
       aspect_ratio: state.aspectRatio,
       fit_mode: state.fitMode || "blur", // Line 92: Safe fallback to "blur"
       ...
     };
   }
   ```

3. **Event Listener Registration (Lines 521–524):**
   ```javascript
   $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
     state.fitMode = button.dataset.fitMode;
     $$(".fit-mode-btn").forEach((item) => item.classList.toggle("selected", item === button));
   }));
   ```
   *Enhancement recommendation*: Add aria-checked synchronization:
   ```javascript
   $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
     state.fitMode = button.dataset.fitMode;
     $$(".fit-mode-btn").forEach((item) => {
       const isSelected = item === button;
       item.classList.toggle("selected", isSelected);
       item.setAttribute("aria-checked", isSelected ? "true" : "false");
     });
   }));
   ```

### 3.3 The Evo Preset Flow Lifecycle

Let's trace what happens when an end user selects and executes an Evo workflow:

```
[User Action]
  │
  ├── 1. User clicks Evo Flagship Card (index.html:266) OR selects Evo in Modal (index.html:494)
  │      └── Triggers selectCaptionStyle("evo") (app.js:560)
  │            ├── Sets state.captionStyle = "evo"
  │            ├── Toggles .caption-card.selected classes
  │            └── Updates indicator #active-caption-name
  │      NOTE: state.fitMode remains untouched -> "blur"
  │
  ├── 2. User selects Prompt Designer chip "Evo Frosted Pill" (index.html:340)
  │      └── Triggers chip click handler (app.js:666)
  │            ├── Sets #caption-prompt-input value
  │            ├── Sets state.captionPrompt = "Frosted glass cyan pill with luminous active pop and top headline banner"
  │            └── Backend parse_caption_prompt() maps "evo", "frosted", "cyan" -> base_key="evo"
  │      NOTE: state.fitMode remains untouched -> "blur"
  │
  ├── 3. User clicks "Find my best clips" (#create-button)
  │      └── Calls createProject() (app.js:106)
  │            ├── Invokes readSettings() -> fit_mode: "blur", caption_style: "evo"
  │            └── Dispatches POST /api/jobs/upload or POST /api/jobs/url
  │
[Backend API: backend/app.py]
  │
  ├── 4. upload_job() / url_job()
  │      └── Receives fit_mode="blur" (Form default or JobPayload default)
  │      └── Invokes create_job(..., fit_mode="blur", caption_style="evo")
  │      └── Stores "fit_mode": "blur" in SQLite job record
  │
[Background Worker: process_job()]
  │
  ├── 5. process_job(job_id)
  │      ├── fit_mode = job.get("fit_mode", "blur") -> "blur"
  │      ├── write_ass(..., caption_style_to_use="evo") -> generates ASS subtitles with frosted pill styling
  │      └── render_clip(..., aspect="9:16", fit_mode="blur")
  │
[FFmpeg Engine: render_clip()]
  │
  └── 6. Executes 2-pass split filtergraph (lines 1297-1306):
         - Background: scale=1080:1920:increase, crop=1080:1920, boxblur=28:5, dimmed
         - Foreground: scale=1080:-2:lanczos, eq, unsharp
         - Overlay: centered foreground over blurred background
         - Subtitles: Evo ASS layer overlay on top of composition
         Result: High-production 9:16 vertical short with ambient blur framing + frosted cyan captions.
```

### 3.4 Backend Route & Execution Flow (`backend/app.py`)

- **Line 269:** `JobPayload.fit_mode: str = "blur"`
- **Line 1259:**
  ```python
  def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str, caption_style: str = "clean", template: str = "podcast", job_id: str | None = None, fit_mode: str = "blur") -> None:
  ```
  *(Recommend updating default argument from `"fit"` to `"blur"`)*
- **Line 1465:** `fit_mode = job.get("fit_mode", "blur")`
- **Line 1501:** `render_clip(..., fit_mode=fit_mode)`
- **Line 1547:** `def create_job(..., fit_mode: str = "blur", ...)`
- **Lines 1556–1557:**
  ```python
  if fit_mode not in {"blur", "letterbox", "crop"}:
      fit_mode = "blur"
  ```
- **Line 1622:** `fit_mode: str = Form("blur")` in `upload_job()`
- **Line 1669:** `fit_mode=payload.fit_mode` in `url_job()`

---

## 4. Specific Recommended Changes

### 4.1 `frontend/index.html`

**Location:** Lines 203–215  
**Action:** Replace button text and add ARIA radio attributes.

```html
<<<< BEFORE
              <div class="fit-mode-options" role="radiogroup" aria-label="Canvas framing mode">
                <button type="button" class="fit-mode-btn selected" data-fit-mode="blur">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 12a4 4 0 0 0 8 0"/></svg>
                  <span>Ambient Blur</span>
                </button>
                <button type="button" class="fit-mode-btn" data-fit-mode="letterbox">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="8" x2="21" y2="8"/><line x1="3" y1="16" x2="21" y2="16"/></svg>
                  <span>Black Bars (No Blur)</span>
                </button>
                <button type="button" class="fit-mode-btn" data-fit-mode="crop">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>
                  <span>Smart Crop (Full Fill)</span>
                </button>
              </div>
==== AFTER
              <div class="fit-mode-options" role="radiogroup" aria-label="Canvas framing mode">
                <button type="button" class="fit-mode-btn selected" data-fit-mode="blur" role="radio" aria-checked="true">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 12a4 4 0 0 0 8 0"/></svg>
                  <span>Canvas Framing (Ambient Blur)</span>
                </button>
                <button type="button" class="fit-mode-btn" data-fit-mode="letterbox" role="radio" aria-checked="false">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="8" x2="21" y2="8"/><line x1="3" y1="16" x2="21" y2="16"/></svg>
                  <span>Black Bars (Letterbox)</span>
                </button>
                <button type="button" class="fit-mode-btn" data-fit-mode="crop" role="radio" aria-checked="false">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>
                  <span>Smart Crop (Center Punch-in)</span>
                </button>
              </div>
>>>>
```

### 4.2 `frontend/app.js`

**Location:** Lines 521–524  
**Action:** Enhance button click listener to update `aria-checked` alongside `selected` class.

```javascript
<<<< BEFORE
  $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
    state.fitMode = button.dataset.fitMode;
    $$(".fit-mode-btn").forEach((item) => item.classList.toggle("selected", item === button));
  }));
==== AFTER
  $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
    state.fitMode = button.dataset.fitMode;
    $$(".fit-mode-btn").forEach((item) => {
      const isSelected = item === button;
      item.classList.toggle("selected", isSelected);
      item.setAttribute("aria-checked", isSelected ? "true" : "false");
    });
  }));
>>>>
```

### 4.3 `backend/app.py`

**Location:** Line 1259  
**Action:** Update default parameter in `render_clip` from `"fit"` to `"blur"`.

```python
<<<< BEFORE
def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str, caption_style: str = "clean", template: str = "podcast", job_id: str | None = None, fit_mode: str = "fit") -> None:
==== AFTER
def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str, caption_style: str = "clean", template: str = "podcast", job_id: str | None = None, fit_mode: str = "blur") -> None:
>>>>
```

---

## 5. Side Effect and Risk Assessment

| Potential Risk | Severity | Mitigation / Reality |
|---|---|---|
| CSS overflow due to longer button text | Low | Verified in CSS rules: `.fit-mode-btn` is a flex column with centered alignment and 11px font size. Text wraps cleanly. |
| Existing job payloads missing `fit_mode` | None | Handled safely by `job.get("fit_mode", "blur")` in `backend/app.py:1465`. |
| API payload breakages | None | Payload schema string values remain identical (`"blur"`, `"letterbox"`, `"crop"`). Only UI display labels change. |
| Existing unit test failures on fit_mode | None | `test_fit_mode_framing_options_in_render_clip` in `tests/test_cutflow.py:351` passes with 0 errors. |

---

## 6. Verification Method

1. **Unit Testing:**
   Run:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover tests/
   ```
   Verify `test_fit_mode_framing_options_in_render_clip` executes and passes (verifies `blur`, `letterbox`, and `crop` FFmpeg filter generation).

2. **Frontend UI Inspection:**
   - Inspect `#create-view`:
   - Verify `[data-fit-mode="blur"]` has `.selected` class and `aria-checked="true"`.
   - Verify text reads `"Canvas Framing (Ambient Blur)"`.
   - Verify `[data-fit-mode="letterbox"]` reads `"Black Bars (Letterbox)"`.
   - Verify `[data-fit-mode="crop"]` reads `"Smart Crop (Center Punch-in)"`.

3. **End-to-End Evo Flow Inspection:**
   - Select Evo caption card (`data-caption-style="evo"`).
   - Verify `readSettings()` returns `{ fit_mode: "blur", caption_style: "evo", ... }`.
   - Submit job; inspect backend job object in SQLite: `fit_mode` is `"blur"`.
   - Inspect FFmpeg execution command in log: contains `-filter_complex` with `boxblur=28:5`.
