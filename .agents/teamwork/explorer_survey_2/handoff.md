# Handoff Report: Survey Explorer 2 (Issue 2 Investigation)

## 1. Observation

- **Test Suite Failure**:
  Command: `.\.venv\Scripts\python.exe -m unittest discover tests/`
  Result: `Ran 31 tests in 0.248s. FAILED (errors=5)`.
  Verbatim errors:
  - `backend/app.py:1084`: `KeyError: 'base_color'` in `write_ass()` for `test_caption_layout_supports_all_output_ratios`, `test_caption_presets_and_phrase_captions_stay_readable`, `test_captions_ai_prime_preset_and_kinetic_pop`, and `test_multi_layer_ass_renders_headline_and_badge_boxes`.
  - `tests/test_cutflow.py:287`: `KeyError: 'show_headline'` in `test_flagship_caption_styles_exist_and_are_emoji_free`.
- **All 18 Styles Affected**:
  Executing `write_ass()` across all 18 styles in `CAPTION_STYLES` (`focus`, `linen`, `evo`, `lift`, `stack`, `align`, `prime`, `impact`, `paper`, `elevate`, `pop`, `y2k`, `chalk`, `clean`, `pulse`, `glow`, `hormozi`, `karaoke`) failed with `KeyError: 'base_color'`.
- **Dictionary Definition**:
  In `backend/app.py` lines 63–80, `CAPTION_STYLES` is generated via a dictionary comprehension over `CAPTION_PRESETS.items()`. It includes:
  `label`, `description`, `font`, `headline_font`, `accent_color`, `caption_box`, `active`, `headline`, `frame`, `zone`, `karaoke`, `uppercase`, `max_words`.
  It lacks:
  `base_color`, `outline_color`, `upcoming_color`, `back_color`, `outline`, `shadow`, `glow`, `show_headline`, `top_banner`, `badge_box`, `pill`, `vertical_side`, `kinetic_pop`.
- **Unprotected Indexing in `write_ass()`**:
  - `backend/app.py:1084`: `Style: Cutflow,{font_name},{base_size},{style["base_color"]},&H000000FF,{style["outline_color"]},{back_color}...`
  - `backend/app.py:1087`: `Style: CutflowBanner,{banner_font},{title_size - 4},&H00141610,&H000000FF,{style["accent_color"]},{style["accent_color"]}...`
  - `backend/app.py:1098`: `accent_color = style["accent_color"]`
  - `backend/app.py:1099`: `base_color = style["base_color"]`
- **Color Discrepancy in `backend/captions/presets.py`**:
  - `backend/captions/presets.py:83` sets `prime` accent to `&H0000FAFF`, whereas `tests/test_cutflow.py:121` asserts `&H00FFFA93`.
  - `backend/captions/presets.py:158` sets `pulse` accent to `&H0000F466`, whereas `tests/test_cutflow.py:102` asserts `&H0066F4C6`.

---

## 2. Logic Chain

1. **Root Cause**: The comprehension defining `CAPTION_STYLES` in `backend/app.py:63-80` does not expose `base_color` (from `CaptionSpec.primary`), `outline_color` (from `spec.outline`), `show_headline` (from `spec.headline != 'none'`), or the other geometry/treatment flags.
2. **Crash Trigger**: Whenever `write_ass()` runs, line 1084 immediately evaluates `style["base_color"]`. Because `base_color` does not exist in any entry of `CAPTION_STYLES`, a `KeyError` is raised immediately before any ASS events are rendered.
3. **Dual Failure Mode**:
   - `write_ass()` crashes on missing `base_color`.
   - `test_cutflow.py:287` crashes on missing `show_headline` on `CAPTION_STYLES["focus"]`.
4. **Resolution Path**:
   - Expanding `CAPTION_STYLES` with the mapped fields bridges declarative `CaptionSpec` values into the dictionary format expected by the renderer and tests.
   - Refactoring lines 1084, 1087, 1098, 1099 in `write_ass()` to use defensive `.get()` with canonical defaults (`&H00FFFFFF`, `&H00111111`, `&H00D5FF5F`) prevents `KeyError` even if callers pass partial custom styles or empty dictionaries.
   - Aligning `pulse` (`&H0066F4C6`) and `prime` (`&H00FFFA93`) accent tokens eliminates assertion mismatches in the test suite.
5. **Validation**: Applying this combined fix in an in-memory test runner executes all 31 unit tests with 0 errors and 0 failures.

---

## 3. Caveats

- `backend/captions/ass.py` contains an alternative ASS generation engine that operates directly on `CaptionSpec`. It is currently imported as `ass_engine` in `backend/app.py:25` but not invoked. The production pipeline uses `write_ass()` in `backend/app.py`.
- No modifications to frontend code or database schemas are needed for Issue 2.
- No other unit tests in `tests/test_cutflow.py` test `write_ass()` for styles other than `pulse`, `prime`, `clean`, and `focus`. Additional regression tests covering all 18 styles are recommended.

---

## 4. Conclusion

- Issue 2 is completely understood and isolated to `backend/app.py` (`CAPTION_STYLES` definition lines 63–80, `write_ass()` lines 1084–1101) and `backend/captions/presets.py` (lines 83 and 158).
- The implementation plan's proposed mapping and defensive `.get()` refactoring is exact, complete, and fully verified.
- The implementer can proceed with confidence to implement Component 1 of the implementation plan.

---

## 5. Verification Method

- **Unit Test Verification**:
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover tests/
  ```
  Expected: `Ran 31 tests in ~0.25s. OK.` (0 failures, 0 errors).
- **Comprehensive 18-Style Verification**:
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -c "import tempfile; from pathlib import Path; from backend.app import write_ass, CAPTION_STYLES; td = tempfile.mkdtemp(); [write_ass(Path(td)/f'{s}.ass', [{'start':0,'end':1,'word':'Hi'}], 0, 1, '9:16', s) for s in CAPTION_STYLES]; print('All 18 rendered OK')"
  ```
  Expected: Prints `All 18 rendered OK` without raising `KeyError`.
- **Invalidation Conditions**:
  Any occurrence of `KeyError: 'base_color'`, `KeyError: 'outline_color'`, `KeyError: 'accent_color'`, or `KeyError: 'show_headline'`.
