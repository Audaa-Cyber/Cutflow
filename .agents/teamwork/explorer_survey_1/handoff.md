# Handoff Report: Survey Explorer 1 (Issue 1)

## 1. Observation

1. **Frontend Framing Options (`frontend/index.html:197-216`)**:
   - Lines 202–215:
     ```html
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
     ```
   - The first button (`data-fit-mode="blur"`) already has the `selected` class, but the button text is `"Ambient Blur"` instead of `"Canvas Framing (Ambient Blur)"`. Button 2 is `"Black Bars (No Blur)"` instead of `"Black Bars (Letterbox)"`, and Button 3 is `"Smart Crop (Full Fill)"` instead of `"Smart Crop (Center Punch-in)"`.

2. **Frontend State & Serialization (`frontend/app.js`)**:
   - Line 4: `fitMode: "blur"` inside `const state = { ... }`.
   - Line 92: `fit_mode: state.fitMode || "blur"` in `readSettings()`.
   - Lines 521–524:
     ```javascript
     $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
       state.fitMode = button.dataset.fitMode;
       $$(".fit-mode-btn").forEach((item) => item.classList.toggle("selected", item === button));
     }));
     ```
   - Selecting caption styles (e.g., Evo flagship card at `frontend/index.html:266` or prompt chip at line 340) triggers `selectCaptionStyle("evo")` or input changes that modify only `state.captionStyle` and `state.captionPrompt`; `state.fitMode` is completely untouched and remains `"blur"`.

3. **Backend Schema, Endpoints, and Processing (`backend/app.py`)**:
   - Line 269: `fit_mode: str = "blur"` in `JobPayload`.
   - Line 1259: `def render_clip(..., fit_mode: str = "fit") -> None:`.
   - Lines 1297–1306: In `render_clip()`, any mismatched aspect with `fit_mode != "crop"` (and not `"letterbox"`) builds the 2-pass `boxblur=28:5` filtergraph overlay.
   - Line 1465: `fit_mode = job.get("fit_mode", "blur")`.
   - Line 1547 & 1556–1557: `create_job` defaults `fit_mode="blur"` and sanitizes invalid values to `"blur"`.
   - Line 1622: `upload_job` defaults `fit_mode: str = Form("blur")`.
   - Line 1669: `url_job` passes `payload.fit_mode`.

4. **Test Suite Status (`tests/test_cutflow.py`)**:
   - Command run: `.\.venv\Scripts\python.exe -m unittest discover tests/`
   - Output: 31 tests ran. 5 failed exclusively due to Issue 2 (`KeyError: 'base_color'` and `KeyError: 'show_headline'`).
   - `test_fit_mode_framing_options_in_render_clip` (line 351) ran and passed with 0 errors, validating `letterbox`, `crop`, and `blur` FFmpeg commands.

---

## 2. Logic Chain

1. From **Observation 1**, `frontend/index.html` already marks `data-fit-mode="blur"` as `selected`. However, the visual label text is `"Ambient Blur"`, which does not explicitly present the branding **"Canvas Framing (Ambient Blur)"** as specified in Requirement R1 and the implementation plan.
2. From **Observation 2**, `frontend/app.js` initializes `state.fitMode` to `"blur"` on boot and safeguards it in `readSettings()`. The selector click handler binds to `button.dataset.fitMode`, not `button.textContent`. Therefore, changing the text of the button in HTML has zero negative impact on JS selection logic.
3. From **Observation 2**, when an end-user triggers the Evo flow (selecting the Evo card or typing/chipping an Evo prompt), `state.fitMode` is neither reset nor overwritten. When `createProject()` is called, `fit_mode: "blur"` is bundled with `caption_style: "evo"`.
4. From **Observation 3**, the backend natively accepts and enforces `fit_mode="blur"`. While `render_clip()` line 1259 defaults `fit_mode: str = "fit"`, changing it to `"blur"` establishes full parameter consistency without breaking any caller.
5. From **Observation 4**, the existing framing filter logic is verified by automated unit tests.

---

## 3. Caveats

- **Issue 2 and Issue 3**: The unit test suite currently fails 5 tests due to Issue 2 (`KeyError: 'base_color'`). Those tests belong to Issue 2 and do not impede or affect Issue 1 investigation.
- **Browser Accessibility**: The buttons in `.fit-mode-options` are styled as buttons inside `role="radiogroup"`. Updating them with `role="radio"` and synchronized `aria-checked` attributes improves screen-reader compliance without altering CSS layout.

---

## 4. Conclusion

Issue 1 implementation is straightforward, high-confidence, and non-breaking:
1. In `frontend/index.html` (lines 203–215):
   - Update button 1 text to `Canvas Framing (Ambient Blur)`. Keep `selected` class and add `role="radio" aria-checked="true"`.
   - Update button 2 text to `Black Bars (Letterbox)`. Add `role="radio" aria-checked="false"`.
   - Update button 3 text to `Smart Crop (Center Punch-in)`. Add `role="radio" aria-checked="false"`.
2. In `frontend/app.js` (lines 521–524):
   - Update the `.fit-mode-btn` click listener to toggle `aria-checked` alongside `selected`.
3. In `backend/app.py` (line 1259):
   - Change `render_clip` signature default parameter from `fit_mode: str = "fit"` to `fit_mode: str = "blur"`.

No database migrations or breaking API modifications are required.

---

## 5. Verification Method

1. **Automated Unit Tests**:
   Execute:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover tests/
   ```
   Verify that `test_fit_mode_framing_options_in_render_clip` passes.
2. **HTML & DOM Inspection**:
   Inspect `frontend/index.html` around line 203:
   - Button 1 has class `fit-mode-btn selected`, attribute `data-fit-mode="blur"`, and text `Canvas Framing (Ambient Blur)`.
   - Button 2 has text `Black Bars (Letterbox)`.
   - Button 3 has text `Smart Crop (Center Punch-in)`.
3. **Evo Workflow Verification**:
   - Open UI, select **Evo** caption card.
   - Verify `readSettings()` produces `{ fit_mode: "blur", caption_style: "evo", ... }`.
   - Submit job and verify that backend rendering invokes `boxblur` canvas framing filter graph for 9:16 vertical output.
