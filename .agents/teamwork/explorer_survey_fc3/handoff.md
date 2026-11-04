# Handoff Report: Requirement R3 — Thorough Testing, Verification, and FFmpeg ASS Rendering

## 1. Observation

### 1.1 Existing Test Suites and Test Runner Commands
1. **Test Suites Overview**:
   - `tests/test_cutflow.py` contains 31 unit tests covering baseline MVP features: templates, candidate ranking, initial caption styling, prompt editing, and SQLite persistence.
   - `tests/test_e2e_features.py` contains 32 test methods (incorporating 18 subtests covering all 18 caption styles) structured across 4 tiers:
     - Tier 1: Canvas Framing Default (R1/F1–F3), Caption Styles Schema & Rendering (R2/F4–F6), Bulk Job Deletion (R3/F7–F9).
     - Tier 2: Boundary, Corner & Adversarial Cases.
     - Tier 3: Cross-Feature Combinations.
     - Tier 4: Real-World Workflows.
   - Total current test count: **63 tests**.

2. **Test Runner Command and Python Environment**:
   - Running `python -m unittest discover tests/` using the system Python (`C:\Users\Nimox\AppData\Local\Programs\Python\Python313\python.exe`) fails with:
     ```
     ImportError: Failed to import test module: test_cutflow
     ModuleNotFoundError: No module named 'fastapi'
     ```
   - A dedicated Python virtual environment is installed at:
     `c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.venv`
   - When executed using the virtualenv Python or with `.venv\Scripts` in `PATH`:
     ```powershell
     .\.venv\Scripts\python.exe -m unittest discover tests/
     # or
     $env:PATH = "$PWD\.venv\Scripts;$env:PATH"; python -m unittest discover tests/
     ```
     Result:
     ```
     Ran 63 tests in 0.999s
     OK
     ```

### 1.2 Inventory of Tests for `write_ass`, Caption Generation, and Clip Rendering
- Direct calls to `write_ass` and subtitle assertions exist in:
  - `tests/test_cutflow.py`:
    - `test_captions_ai_palette_and_subtitle_geometry` (lines 90–110): Calls `write_ass(subtitle, words, 0, 8, "9:16", "pulse")`. Asserts `PlayResY: 1920`, `Montserrat`, `MarginV`, `\c&H0066F4C6`, `\fscx114\fscy114`, `len(visible_caption) <= 28`.
    - `test_captions_ai_prime_preset_and_kinetic_pop` (lines 111–125): Calls `write_ass(subtitle, words, 0, 1.5, "9:16", "prime", auto_emoji=True, kinetic_pop=True)`. Asserts `\c&H00FFFA93`, `\fscx114\fscy114`, emojis `⚡`, `🚀`.
    - `test_caption_layout_supports_all_output_ratios` (lines 143–151): Calls `write_ass(subtitle, words, 0, 2, aspect, "clean")` for `"9:16"`, `"1:1"`, `"16:9"`. Asserts `PlayResY: 1920`, `PlayResY: 1080`, `PlayResX: 1920`.
    - `test_multi_layer_ass_renders_headline_and_badge_boxes` (lines 315–329): Calls `write_ass(subtitle, words, 0, 1.5, "9:16", "focus", auto_headline=True)`. Asserts `CutflowTitle`, `THE BIGGEST MISTAKE`, and inline tag `\3c&H00FFFFFF\c&H00000000`.
  - `tests/test_e2e_features.py`:
    - `test_all_18_caption_styles_render_ass_without_error` (lines 215–238): Subtests all 18 preset keys, calling `write_ass(...)`. Asserts `[Script Info]`, `[V4+ Styles]`, `Style: Cutflow,`, `[Events]`, and `Dialogue:` lines.
    - `test_write_ass_with_sparse_custom_style_defensive_fallbacks` (lines 423–442): Tests `{}` empty, `{"font": ...}`, and `{"accent_color": ...}`. Asserts `Style: Cutflow,` and `&H00FFFFFF`.
    - `test_write_ass_with_none_or_missing_color_keys` (lines 443–461): Tests `None` values for color keys. Asserts `Style: Cutflow,`.
    - `test_write_ass_with_invalid_style_key_fallback` (lines 462–473): Tests unknown style key fallback. Asserts `out_file.exists()`.
    - `test_write_ass_handles_empty_words_gracefully` (lines 493–506): Tests empty words list `[]`. Asserts valid `[Script Info]`, `[V4+ Styles]`.
    - `test_write_ass_escaping_and_special_characters` (lines 507–527): Tests braces `{}`, backslashes `\`, emojis, and quotes. Asserts `[Events]` and dialogue lines.
    - `test_evo_preset_with_default_canvas_framing` (lines 564–581): Calls `write_ass(..., caption_style="evo")`. Asserts `\fscx114\fscy114`.
    - `test_e2e_full_job_pipeline_lifecycle` (lines 650–701): Calls `write_ass(..., caption_style="linen")`. Asserts font `Merriweather`.
    - `test_prompt_designer_evo_chip_workflow` (lines 703–726): Calls `write_ass(..., custom_style=custom_style)`. Asserts `Style: Cutflow,`.
- Clip rendering tests calling `render_clip()`:
  - `tests/test_cutflow.py:152`: `test_render_pipeline_uses_subtle_finishing_and_preserves_audio` (mocks `run_command`, asserts `eq=`, `unsharp=`, `ass=`).
  - `tests/test_e2e_features.py:67`: `test_render_clip_signature_default_fit_mode_is_blur` (verifies default parameter `fit_mode="blur"`).
  - `tests/test_e2e_features.py:73`: `test_render_clip_omitted_fit_mode_executes_ambient_blur_filter` (verifies `-filter_complex` with `boxblur=28:5`).
  - `tests/test_e2e_features.py:480`: `test_render_clip_invalid_fit_mode_falls_back_to_blur`.
  - `tests/test_e2e_features.py:564`: `test_evo_preset_with_default_canvas_framing` (verifies combination of evo preset with `render_clip`).
  - `tests/test_e2e_features.py:650`: `test_e2e_full_job_pipeline_lifecycle`.

### 1.3 `compile_ass` Compiler Implementation vs Legacy `write_ass`
1. **Module Location**: `backend/captions/ass.py` (lines 661–697):
   ```python
   def compile_ass(spec, *, words: list[dict], start: float, end: float,
                   aspect: str, auto_emoji: bool = False, emoji_map: dict | None = None,
                   auto_headline: bool = True, headline_text: str | None = None,
                   hook_duration: float | None = None, candidate_text: str = "",
                   template: str = "podcast", extract_headline=None) -> str:
   ```
2. **Key Differences**:
   - `write_ass(path, words, start, end, aspect, caption_style=..., ...)` accepts a `Path` as first parameter and writes directly to disk.
   - `compile_ass(spec, ...)` accepts a `CaptionSpec` instance (resolved from `backend.captions.presets.PRESETS`) as its first parameter and returns an ASS script `str`.
   - `write_ass` uses legacy style names `Style: Cutflow,` and `Style: CutflowTitle,`.
   - `compile_ass` generates semantic V4+ styles:
     - `Caption` (primary dialogue)
     - `CaptionBadge` and `CaptionBadgeActive` (inverted dialogue badges for `focus` style)
     - `CutHeadline` and `CutBadgeHeadline` (Zone 1 hooks)
     - `CutRail` (Zone 3 side rail)
     - `CutFrame` (Zone 3 border, letterbox, grid, and scanlines)
   - `compile_ass` uses multi-zone layering (Layer 0: Frame, Layer 1: Pill/Marker backing, Layer 2: Headline/Hook, Layer 3: Side rail, Layer 4: Caption dialogue text).

### 1.4 FFmpeg ASS Filter Execution and Windows Path Escaping
1. **Execution in `render_clip` (`backend/app.py:1276–1348`)**:
   - `render_clip` uses FFmpeg's native `ass` video filter (NOT the generic `subtitles` filter):
     ```python
     ass_path = subtitle_path.resolve().as_posix().replace(":", r"\:")
     fonts_dir = FONTS_DIR.resolve().as_posix().replace(":", r"\:")
     ass_filter = f"ass='{ass_path}':fontsdir='{fonts_dir}'"
     ```
   - Simple filter chain (`fit_mode == "letterbox"` or `"crop"`):
     `ffmpeg ... -vf "scale=...:flags=...,unsharp=...,ass='...':fontsdir='...'"`
   - Complex filtergraph (`fit_mode == "blur"`, default 9:16 canvas framing):
     `ffmpeg ... -filter_complex "[0:v]...boxblur...[bg];[0:v]...[fg];[bg][fg]overlay...[comp];[comp]ass='...':fontsdir='...'[vout]" -map "[vout]" -map "0:a?"`
2. **Windows Path Escaping Mechanism**:
   - `.resolve().as_posix()` converts Windows backslashes `\` to standard forward slashes `/` (e.g. `C:/Users/Nimox/...`).
   - `.replace(":", r"\:")` escapes the drive letter colon with a backslash `\:` so FFmpeg's filter option parser does not treat `C:` as an option separator.
   - Enclosing the path in single quotes (`'...'`) protects spaces and punctuation in the path string.
3. **Font Directory and libass Font Loading**:
   - `FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"`.
   - Contains: `JetBrainsMono-Bold.ttf`, `JetBrainsMono-Regular.ttf`, `Merriweather-Bold.ttf`, `Merriweather-Regular.ttf`, `Montserrat-Black.ttf`, `Montserrat-Bold.ttf`, `Montserrat-Regular.ttf`.
   - FFmpeg log confirmed during probing:
     ```
     [Parsed_ass_0 @ ...] libass API version: 0x1705000
     [Parsed_ass_0 @ ...] Loading font file '.../backend/assets/fonts\Montserrat-Bold.ttf'
     [Parsed_ass_0 @ ...] Loading font file '.../backend/assets/fonts\Merriweather-Bold.ttf'
     [Parsed_ass_0 @ ...] Loading font file '.../backend/assets/fonts\JetBrainsMono-Bold.ttf'
     [Parsed_ass_0 @ ...] Using font provider directwrite (with GDI)
     ```
4. **Empirical FFmpeg Rendering Verification across All 18 Presets**:
   - Ran `probe_ffmpeg.py` testing all 18 presets across all 3 aspect ratios (`9:16`, `1:1`, `16:9`) = **54 total test renders** using real FFmpeg invocations with the `ass` filter on synthetic video (`-f lavfi -i color=c=black:s=...:d=0.2:r=25`).
   - Result:
     ```
     Tested 54 combinations.
     Errors count: 0
     Warnings count: 0
     ```

---

## 2. Logic Chain

1. **Test Runner Dependency Chain**:
   - Observation 1.1 shows that `python -m unittest discover tests/` fails under the system Python with `ModuleNotFoundError: No module named 'fastapi'`, but succeeds cleanly with `.\.venv\Scripts\python.exe` (63 passed).
   - Therefore, any CI/CD script or local verification command must run through the project virtual environment `.\.venv\Scripts\python.exe` or have `$env:PATH = "$PWD\.venv\Scripts;$env:PATH"` active.

2. **Pipeline Refactoring Impact (R1 & R2)**:
   - In `backend/app.py`, `write_ass` is currently called in two locations:
     - `process_job()` line 1503 (rendering pipeline for candidate clips).
     - `GET /api/jobs/{job_id}/clips/{filename}` line 1733 (on-the-fly ASS generation for clip downloads).
   - Replacing these calls with `backend.captions.ass.compile_ass(...)` resolving `spec` from `backend.captions.presets.PRESETS` fulfills R1 and connects multi-zone layout compilation (R2).
   - `compile_ass` takes `spec: CaptionSpec` and returns a string `str`. The caller in `backend/app.py` must write `ass_path.write_text(ass_content, encoding="utf-8")`.

3. **Backward Compatibility and Test Breakage Analysis**:
   - Multiple unit tests in `tests/test_cutflow.py` and `tests/test_e2e_features.py` import and call `write_ass` directly.
   - If `write_ass` is deleted outright from `backend/app.py`:
     - Both `test_cutflow.py` and `test_e2e_features.py` will fail immediately on import (`ImportError: cannot import name 'write_ass' from 'backend.app'`).
   - If `write_ass` is retained as a compatibility facade that delegates to `compile_ass`:
     - Test `test_multi_layer_ass_renders_headline_and_badge_boxes` (`test_cutflow.py:315`) asserts:
       - `CutflowTitle` in content (Fails: `compile_ass` uses `CutHeadline` and `CutBadgeHeadline`).
       - `\3c&H00FFFFFF\c&H00000000` in content (Fails: `compile_ass` uses `CaptionBadge` style and per-word badge classes, not inline `\3c...\c` tags).
     - Tests in `test_e2e_features.py`:
       - `test_all_18_caption_styles_render_ass_without_error` (`test_e2e_features.py:234`) asserts `Style: Cutflow,` in content (Fails: `compile_ass` uses `Style: Caption,`).
       - `test_write_ass_with_sparse_custom_style_defensive_fallbacks` (`test_e2e_features.py:440`) asserts `Style: Cutflow,` in content.
       - `test_write_ass_with_none_or_missing_color_keys` (`test_e2e_features.py:460`) asserts `Style: Cutflow,` in content.
       - `test_prompt_designer_evo_chip_workflow` (`test_e2e_features.py:725`) asserts `Style: Cutflow,` in content.
   - Therefore, there are two distinct design strategies:
     - **Strategy A (Strict Contract Updates)**: Update the tests to assert the true modern multi-zone styles (`Style: Caption,`, `CutHeadline`, `CaptionBadge`) and update `write_ass` to delegate to `compile_ass`.
     - **Strategy B (Compatibility Aliasing)**: In `compile_ass` (or in a `write_ass` wrapper), emit alias style rows (e.g. `Style: Cutflow,...` aliased to `Caption`, and `Style: CutflowTitle,...` aliased to `CutHeadline`).
     - Strategy A is cleaner and strictly reflects the multi-zone architecture, but requires small localized updates to the 5 test assertions. Strategy B avoids test edits. Strategy A + updating tests is recommended as it aligns directly with Requirement R1/R2.

4. **Multi-Zone Burn-In and Libass Reliability**:
   - The ASS specification allows vector drawing commands (`\p1 ... \p0`) on lower layers (Layer 0 for frame/letterbox/grid/scanlines, Layer 1 for pills/markers, Layer 2 for banner backings) while dialogue text resides on Layer 4.
   - Empirical probing confirmed that libass v0.17.5 handles all vector paths (`rounded_rect`, `subrect`), scanline repetitions, dynamic alpha fading (`\fad`), and kinetic pops (`\fscx114\fscy114`) without memory errors, syntax parsing errors, or rendering artifacts.
   - Escaping `:` with `\:` and wrapping paths in single quotes inside the `-filter_complex` string guarantees cross-platform compatibility on Windows.

---

## 3. Caveats

1. **System Python vs Virtualenv Python**:
   - The environment variable `PATH` in a raw Windows shell defaults to system Python (where `fastapi` is not installed). All automated runners must explicitly invoke `.\.venv\Scripts\python.exe` or activate `.venv`.
2. **Unicode BOM in Source Files**:
   - `backend/captions/ass.py` previously contained a UTF-8 BOM (`\ufeff`) at byte 0. While Python's standard `import` handles UTF-8 BOM automatically, tools reading with `open(..., encoding="utf-8")` (without `-sig`) or certain AST parsers may raise a `SyntaxError` on line 1.
3. **GPU Hardware Acceleration**:
   - Test runs use `-c:v libx264 -preset ultrafast` on CPU. Production deployments using NVENC or VAAPI must ensure subtitle burning remains in software filter chains (`libass` is CPU-based) before hardware encoding.

---

## 4. Conclusion

1. **Test Suite Status**:
   - The test infrastructure has 63 tests across `tests/test_cutflow.py` and `tests/test_e2e_features.py`. All 63 pass cleanly when invoked with `.\.venv\Scripts\python.exe -m unittest discover tests/`.
2. **Tests Requiring Updates when `write_ass` is replaced with `compile_ass`**:
   - `tests/test_cutflow.py`:
     - `test_multi_layer_ass_renders_headline_and_badge_boxes`: Replace assertions on legacy strings `"CutflowTitle"` and `r"\3c&H00FFFFFF\c&H00000000"` with `CutHeadline`/`CutBadgeHeadline` and `CaptionBadge`.
   - `tests/test_e2e_features.py`:
     - `test_all_18_caption_styles_render_ass_without_error`: Update assertion `self.assertIn("Style: Cutflow,", content)` to `self.assertIn("Style: Caption,", content)`.
     - `test_write_ass_with_sparse_custom_style_defensive_fallbacks`: Update assertion to `Style: Caption,`.
     - `test_write_ass_with_none_or_missing_color_keys`: Update assertion to `Style: Caption,`.
     - `test_prompt_designer_evo_chip_workflow`: Update assertion to `Style: Caption,`.
   - Furthermore, `write_ass` in `backend/app.py` should be retained as a compatibility wrapper around `compile_ass` so existing tests importing `write_ass` continue to function seamlessly.
3. **FFmpeg ASS Rendering Verification**:
   - `render_clip` correctly uses the `ass='<escaped_path>':fontsdir='<escaped_fontsdir>'` filter with Windows path escaping.
   - All 18 caption styles across all 3 aspect ratios (`9:16`, `1:1`, `16:9`) render cleanly without process failures, libass warnings, or syntax errors.

---

## 5. Verification Method

To independently verify all findings and test suites:

1. **Verify Unit Test Suite**:
   Execute the following command in PowerShell:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover tests/
   ```
   **Expected**: 63 tests run and pass with `OK` (0 failures, 0 errors).

2. **Verify Full-Canvas Compilation Across All 18 Presets**:
   Execute:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   from backend.captions.presets import PRESETS
   from backend.captions.ass import compile_ass
   words = [{'start': 0.0, 'end': 0.5, 'word': 'Test'}, {'start': 0.5, 'end': 1.0, 'word': 'Full-Canvas'}]
   for k, spec in PRESETS.items():
       s = compile_ass(spec, words=words, start=0.0, end=1.0, aspect='9:16', auto_headline=True)
       assert '[Script Info]' in s and 'Style: Caption,' in s
   print('All 18 presets compiled successfully with compile_ass.')
   "
   ```

3. **Verify FFmpeg Multi-Zone ASS Burn-In (54 Combinations)**:
   Execute the probe script located in this agent's folder:
   ```powershell
   .\.venv\Scripts\python.exe .agents/teamwork/explorer_survey_fc3/probe_ffmpeg.py
   ```
   **Expected**: Output displays `Tested 54 combinations. Errors count: 0 Warnings count: 0`.

4. **Invalidation Conditions**:
   - Any test runner invocation failing due to `ModuleNotFoundError` indicates the venv Python was bypassed.
   - Any assertion failure on `Style: Cutflow,` indicates legacy `write_ass` style names are being checked against modern `compile_ass` output.
   - Any FFmpeg exit code != 0 indicates path escaping or filtergraph syntax errors on Windows.
