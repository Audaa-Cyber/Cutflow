# Forensic Audit Report: Milestone 1 — Canvas Framing Default

**Work Product**: Milestone 1 changes (`frontend/index.html`, `frontend/app.js`, `backend/app.py`)  
**Profile**: General Project (Integrity Mode: Development)  
**Verdict**: **CLEAN**

---

### Phase Results
- **Hardcoded Output Detection**: PASS — No hardcoded test results, test strings, or bypass outputs detected in source code.
- **Facade Detection**: PASS — No facade implementations, empty stubs, or mock delegations found. All functions contain genuine computation.
- **Pre-populated Artifact Detection**: PASS — No fake logs, synthetic verification files, or pre-computed results in the workspace.
- **Build & Execution Verification**: PASS — `node --check frontend/app.js` exited 0; unit test `tests.test_cutflow.CutflowTests.test_fit_mode_framing_options_in_render_clip` ran and passed (OK).
- **Behavioral & Parameter Verification**: PASS — `render_clip` signature parameter `fit_mode` defaults to `'blur'`; invoking `render_clip` with default arguments builds the `boxblur=28:5` filtergraph.
- **UI & Accessibility Verification**: PASS — `frontend/index.html` implements `role="radiogroup"`, `role="radio"`, `aria-checked`, and exact button labels. `frontend/app.js` synchronizes state and ARIA attributes dynamically on click.

---

## 1. Observation

1. **`backend/app.py` signature and defaults (line 1259)**:
   ```python
   def render_clip(source: Path, output: Path, subtitle_path: Path, start: float, end: float, aspect: str, caption_style: str = "clean", template: str = "podcast", job_id: str | None = None, fit_mode: str = "blur") -> None:
   ```
   Verified via Python inspect:
   `.\.venv\Scripts\python.exe -c "import inspect; from backend.app import render_clip; sig = inspect.signature(render_clip); print('param:', sig.parameters['fit_mode']); assert sig.parameters['fit_mode'].default == 'blur'"`
   Output: `param: fit_mode: 'str' = 'blur'` (exit code 0).

2. **`backend/app.py` execution with default arguments (filtergraph generation)**:
   Invoked `render_clip(Path('test.mp4'), Path('out.mp4'), Path('sub.ass'), 0.0, 5.0, '9:16')` with mocked `run_command`:
   FFmpeg command executed with `-filter_complex` containing:
   `[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:5,eq=brightness=-0.12:contrast=1.06[bg];[0:v]scale=1080:-2:flags=lanczos,eq=contrast=1.04:saturation=1.06:brightness=0.005,unsharp=5:5:0.25:3:3:0.0[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[comp];[comp]ass='sub.ass':fontsdir='fonts'[vout]`
   Output: `SUCCESS: render_clip default invokes boxblur filtergraph!` (exit code 0).

3. **`backend/app.py` pipeline plumbing**:
   - `JobPayload` schema (line 269): `fit_mode: str = "blur"`
   - `create_job` (lines 1547, 1556-1557, 1572): defaults `fit_mode: str = "blur"`, sanitizes with `if fit_mode not in {"blur", "letterbox", "crop"}: fit_mode = "blur"`, stores in job dict.
   - `upload_job` (lines 1622, 1653): `fit_mode: str = Form("blur")` passed to `create_job`.
   - `url_job` (line 1669): `fit_mode=payload.fit_mode` passed to `create_job`.
   - `process_job` (lines 1465, 1501): extracts `fit_mode = job.get("fit_mode", "blur")` and passes `fit_mode=fit_mode` to `render_clip`.

4. **`frontend/index.html` markup (lines 202–216)**:
   ```html
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
   ```

5. **`frontend/app.js` event handling and state (lines 4, 92, 521–528)**:
   - Line 4: `fitMode: "blur"` initialized in `state`.
   - Line 92: `fit_mode: state.fitMode || "blur"` read in `readSettings()`.
   - Lines 521–528:
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
   - Evo preset selection: `selectCaptionStyle("evo")` only modifies `state.captionStyle = "evo"`, leaving `state.fitMode` as `"blur"`.
   - Script syntax verification command: `node --check frontend/app.js` (exit code 0).

6. **Edge Case & Adversarial Verifications**:
   - Letterbox verification: `fit_mode="letterbox"` generates `pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black` without boxblur filter. (PASS)
   - Crop verification: `fit_mode="crop"` generates `crop=1080:1920` without boxblur filter. (PASS)
   - Square 1:1 aspect ratio verification: generates `boxblur=24:4` with `dim_amount=-0.10`. (PASS)
   - Unrecognized fit_mode fallback: `fit_mode="invalid_fit"` safely falls back to `boxblur=28:5`. (PASS)

---

## 2. Logic Chain

1. From Observation 1, `render_clip`'s signature explicitly specifies `fit_mode: str = "blur"`, aligning with Requirement R1 and PROJECT.md Feature F3.
2. From Observation 2, when `render_clip` is invoked without explicit `fit_mode`, the filter graph builder dynamically executes the ambient blur pipeline (`boxblur=28:5` for 9:16), confirming that the implementation is genuine and functional rather than a facade.
3. From Observation 3, the backend data flow consistently carries the `"blur"` default from Pydantic schemas through route endpoints (`upload_job`, `url_job`), job factory (`create_job`), background runner (`process_job`), and into `render_clip`.
4. From Observation 4, `frontend/index.html` provides the exact requested button labels ("Canvas Framing (Ambient Blur)", "Black Bars (Letterbox)", "Smart Crop (Center Punch-in)") and conforms to WAI-ARIA standards with `role="radiogroup"`, `role="radio"`, and `aria-checked`.
5. From Observation 5, `frontend/app.js` initializes `state.fitMode = "blur"`, synchronizes ARIA states dynamically on user interaction, and preserves the blur default when selecting the Evo preset flow.
6. From Observation 6, adversarial stress testing confirmed that edge cases (letterbox, crop, 1:1 ratio, and fallback on unrecognized modes) behave strictly according to specification.

---

## 3. Caveats

- As noted in `PROJECT.md` and Worker M1 handoff, running the full unit test suite `.\.venv\Scripts\python.exe -m unittest discover tests/` produces 5 failures/errors in caption tests (`KeyError: 'base_color'`). These errors are pre-existing issues scheduled for Milestone 2 (Issue 2) and do not stem from or affect Milestone 1 code changes.

---

## 4. Conclusion

Milestone 1 work product passes all forensic integrity checks under Development Mode.
- No hardcoded test results, facade implementations, or fabricated outputs exist.
- Canvas Framing (Ambient Blur) is genuinely implemented as the system-wide default across frontend markup, frontend state management, API routes, and backend video rendering.
- Binary verdict: **CLEAN**.

---

## 5. Verification Method

To independently reproduce this forensic audit:

1. **Verify `render_clip` signature default**:
   ```powershell
   .\.venv\Scripts\python.exe -c "import inspect; from backend.app import render_clip; assert inspect.signature(render_clip).parameters['fit_mode'].default == 'blur'"
   ```

2. **Verify ambient blur filter execution**:
   ```powershell
   .\.venv\Scripts\python.exe -c "from unittest.mock import patch; from pathlib import Path; from backend.app import render_clip;
   with patch('backend.app.run_command') as mock_run:
       render_clip(Path('test.mp4'), Path('out.mp4'), Path('sub.ass'), 0.0, 5.0, '9:16')
       cmd = [c for c in mock_run.call_args_list if c.args[0][0] == 'ffmpeg'][0].args[0]
       assert 'boxblur=28:5' in cmd[cmd.index('-filter_complex') + 1]
       print('Verification SUCCESS!')"
   ```

3. **Verify framing options unit test**:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest tests.test_cutflow.CutflowTests.test_fit_mode_framing_options_in_render_clip
   ```

4. **Verify frontend syntax**:
   ```powershell
   node --check frontend/app.js
   ```
