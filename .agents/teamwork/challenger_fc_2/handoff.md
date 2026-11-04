# Empirical Verification and Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: LOW
**Verdict**: **APPROVE**

The multi-zone full-canvas caption compilation and rendering pipeline in `backend/captions/` and `backend/app.py` has been subjected to rigorous, code-executing adversarial stress testing across all 4 spatial canvas zones, 18 caption presets, 4 video frame rates (24, 25, 30, 60 fps), multiple clip durations (0.5s – 5.0s), 3 aspect ratios (`9:16`, `1:1`, `16:9`), and all 3 background fit modes (`blur`, `letterbox`, `crop`). All 72 unit/adversarial tests pass with zero failures and zero errors. FFmpeg video filtergraph burn-in completed with exit code 0 and zero warnings on stderr across all 18 styles.

---

## 1. Observation

### 1.1 Multi-Zone Layer Feature Verification
Direct empirical verification was performed via Python execution of `compile_ass()` and `resolve()` across all 18 presets:

1. **Zone 1 (Hook Headline / Banner / Fade)**:
   - `lift` (`headline="banner"`): Emits Layer 2 `CutFrame` drawing event with `rounded_rect` vector path anchor 8 at `pos(540, 127)`, followed by Layer 3 `CutHeadline` text event with anchor 8, dark text `\c&H00141610`, and `\fad(220,420)`.
   - `focus` (`headline="badge"`): Emits Layer 2 `CutBadgeHeadline` text event with `\an8\pos(...)`, `BorderStyle=3`, and `\fad(220,420)`.
   - `stack`, `linen`, `evo`: Emit Layer 2 `CutHeadline` with anchor 8 and `\fad(220,420)`.
   - Fallback headline rendering: With `words=[]` and `candidate_text="FALLBACK TITLE"`, `compile_ass()` emits the Zone 1 headline card cleanly.
   - Headline suppression: Presets with `headline="none"` (`clean`, `pulse`, `glow`, `hormozi`, `karaoke`) or invocations with `auto_headline=False` produce zero headline dialogue events.

2. **Zone 2 (Kinetic Dialogue / Pills / Underlines / Markers / Punch / Badges)**:
   - Vector pill rendering (`evo`, `paper`, `karaoke`): Layer 1 `CutFrame` drawing with `\p1`, anchor 2 `\an2\pos(cx, res.caption_y)`, and bezier path `m ... l ... b ...`.
   - Active underline rendering (`lift`, `align`, `elevate`, `pop`): Layer 1 `CutFrame` drawing with `\an7\pos(left, y)` where `y = res.caption_y + res.cap_px * 0.42` using `subrect(0, 0, width, h)`. Underlines are anchored immediately below the word baseline (e.g. `y = 1799.04` on 1920h canvas for `align`), completely eliminating the historical double-offset bug.
   - Marker highlights (`y2k`, `chalk`): Layer 1 `CutFrame` drawing with `\an2\pos(left - pad + width / 2, res.caption_y)` with `rounded_rect(...)` and opacity 0.30.
   - Active color punch (`\fscx114\fscy114`): Presets with `active_pop=True` (`prime`, `hormozi`, `pop`) emit punch tags around active words. In presets using vector underlines or markers (`lift`, `align`, `chalk`), `active_pop` is bypassed in text runs to avoid misaligning text scale with underline/marker vector geometry.
   - Per-word badge box spacing (`focus`): Inter-token spaces `" "` are preserved so `BorderStyle=3` bounding boxes do not merge. Overrides `\rCaptionBadge` and `\rCaptionBadgeActive` are styled with `\3c{badge_outline}\c{spec.fill_text}`.
   - Bracket closing (`stack`): Indexing `spec.bracket[-1]` produces properly closed brackets `[WORD]`.

3. **Zone 3 (Frame / Rails)**:
   - Side rails: Layer 3 `CutRail` with `\fad(220,420)\an7\pos(56, rail_y)` correctly emitted for `stack` (`"CUTFLOW // MOTION GRAPHICS"`) and `y2k` (`"Y2K // SIGNAL"`). Suppressed on all other presets.
   - Vector frames on Layer 0:
     - `align`: Letterbox top and bottom bars (`CutFrame`, anchor 7, `pos=(0, 0)`).
     - `stack`: 3x3 Grid crosshair rays + 8 corner bracket arms.
     - `y2k`: Horizontal scanlines spanning full canvas height.
     - `linen`, `chalk`, `elevate`: Hairline rules above and below dialogue.

4. **Zone 4 (Safe Margins and Downscaling)**:
   - Safe margins: Across all presets with `zone="lower"`, `caption_y = int(round(height - spec.lower_margin * height))` leaves a bottom clearance between 14% and 22% (e.g., 326px on a 1080x1920 canvas) for mobile platform UI elements. Text is bottom-anchored at `\an2`.
   - Dynamic downscale limits: Long dialogue lines trigger downscaling in `metrics()` that respects a strict floor of `int(base * 0.58)`. Tested with a 19-word sentence: font size stayed >= 53px (initial 92px * 0.58).

---

### 1.2 FFmpeg Synthetic Video Stress Matrix Results
Synthetic source videos were generated via FFmpeg `testsrc2` + `anullsrc` and rendered through `render_clip()` with full video/audio pipelines:

| # | Test Scenario | FPS | Duration | Aspect | Fit Mode | Preset / Condition | Result | Elapsed | Output Size |
|---|---------------|-----|----------|--------|----------|-------------------|--------|---------|-------------|
| 1 | Cinema 24fps short | 24 | 0.5s | 9:16 | blur | `focus` (per-word badge) | **PASS** | 1.60s | 242,930 B |
| 2 | Cinema 24fps 1:1 | 24 | 4.0s | 1:1 | letterbox | `lift` (banner + underline) | **PASS** | 1.58s | 686,569 B |
| 3 | PAL 25fps widescreen | 25 | 1.5s | 16:9 | crop | `stack` (grid + rail) | **PASS** | 3.40s | 1,224,585 B |
| 4 | PAL 25fps vertical | 25 | 4.0s | 9:16 | blur | `align` (letterbox + underline) | **PASS** | 10.81s | 887,426 B |
| 5 | Web 30fps square | 30 | 0.5s | 1:1 | crop | `evo` (pill + cyan glow) | **PASS** | 0.60s | 637,252 B |
| 6 | Web 30fps cyber | 30 | 2.0s | 9:16 | blur | `y2k` (scanlines + marker) | **PASS** | 4.64s | 516,858 B |
| 7 | Web 30fps sketch | 30 | 5.0s | 9:16 | letterbox | `chalk` (rules + marker) | **PASS** | 6.17s | 881,659 B |
| 8 | Web 30fps editorial | 30 | 3.0s | 16:9 | letterbox | `linen` (editorial rules) | **PASS** | 4.03s | 2,652,368 B |
| 9 | High 60fps kinetic | 60 | 1.0s | 9:16 | blur | `prime` (kinetic punch) | **PASS** | 4.02s | 281,273 B |
| 10 | High 60fps square | 60 | 4.0s | 1:1 | blur | `paper` (cream pill) | **PASS** | 7.49s | 992,036 B |
| 11 | High 60fps punch | 60 | 2.5s | 9:16 | crop | `hormozi` (2-word pop) | **PASS** | 3.32s | 1,380,158 B |
| 12 | Web 30fps clean | 30 | 3.0s | 9:16 | blur | `clean` (minimal static) | **PASS** | 4.49s | 710,368 B |
| 13 | Fallback empty words | 30 | 2.0s | 9:16 | blur | `focus` (`words=[]`) | **PASS** | 2.97s | 485,869 B |
| 14 | Custom prompt style | 30 | 2.0s | 9:16 | blur | `clean` (pill + banner) | **PASS** | 3.18s | 486,780 B |
| 15 | Unicode & emojis | 30 | 3.0s | 9:16 | blur | `prime` (accents + emojis) | **PASS** | 4.47s | 734,871 B |
| 16 | Rapid fire speech | 30 | 1.0s | 9:16 | blur | `focus` (50ms tokens) | **PASS** | 1.65s | 264,556 B |
| 17 | Vertical source to 9:16 | 30 | 1.0s | 9:16 | blur | `lift` (non-mismatch path) | **PASS** | 0.78s | 930,723 B |

Every generated video was inspected with `ffprobe` to verify that resolution matched the target dimensions exactly (`1080x1920`, `1080x1080`, `1920x1080`), audio and video streams were multiplexed properly, and file sizes were non-zero.

---

### 1.3 FFmpeg Stderr Hygiene Audit Across All 18 Presets
FFmpeg was executed with `-loglevel warning` on all 18 caption presets burning into 1080x1920 synthetic video:
- `focus`: exit code 0, 0 stderr warnings (932,824 B)
- `linen`: exit code 0, 0 stderr warnings (1,011,051 B)
- `evo`: exit code 0, 0 stderr warnings (992,029 B)
- `lift`: exit code 0, 0 stderr warnings (992,073 B)
- `stack`: exit code 0, 0 stderr warnings (975,702 B)
- `align`: exit code 0, 0 stderr warnings (950,031 B)
- `prime`: exit code 0, 0 stderr warnings (999,988 B)
- `impact`: exit code 0, 0 stderr warnings (949,539 B)
- `paper`: exit code 0, 0 stderr warnings (973,004 B)
- `elevate`: exit code 0, 0 stderr warnings (1,013,287 B)
- `pop`: exit code 0, 0 stderr warnings (998,608 B)
- `y2k`: exit code 0, 0 stderr warnings (1,061,468 B)
- `chalk`: exit code 0, 0 stderr warnings (1,014,242 B)
- `clean`: exit code 0, 0 stderr warnings (990,125 B)
- `pulse`: exit code 0, 0 stderr warnings (989,449 B)
- `glow`: exit code 0, 0 stderr warnings (987,252 B)
- `hormozi`: exit code 0, 0 stderr warnings (931,339 B)
- `karaoke`: exit code 0, 0 stderr warnings (981,940 B)

**Result**: ZERO filtergraph parsing errors, ZERO font resolution errors, ZERO libass syntax warnings.

---

### 1.4 Test Suite Pass Status
Executed test suite:
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests/
```
Result:
```
........................................................................
----------------------------------------------------------------------
Ran 72 tests in 11.065s

OK
```
Zero failures, zero errors across all 72 tests in `tests/test_cutflow.py`, `tests/test_e2e_features.py`, and `tests/test_adversarial_challenger.py`.

---

## 2. Logic Chain

1. **Zone 1 Headline Correctness**:
   - `compile_ass` resolves headline styles into `CutHeadline` or `CutBadgeHeadline`.
   - Banner treatments generate a rounded-rect backing box on Layer 2 (`CutFrame`) and contrasting dark text on Layer 3 (`CutHeadline`).
   - Fades use `\fad(220,420)`, ensuring smooth visual transitions without filter errors.
   - Fallback candidate clips (`words = []`) render topic cards when `auto_headline=True` and `candidate_text` or `headline_text` is supplied.

2. **Zone 2 Kinetic Dialogue Geometry**:
   - Anchoring underlines at `\an7\pos(left, y)` with `y = res.caption_y + res.cap_px * 0.42` and `paths=[subrect(0, 0, width, h)]` places the underline precisely below the word baseline inside visible canvas bounds.
   - Per-word badge box spacing explicitly adds a space token `" "` between badge tokens, preventing libass from merging adjacent `BorderStyle=3` boxes.
   - Text punch tags `\fscx114\fscy114` are cleanly applied for popping text and correctly bypassed for underlined or marker-highlighted words to avoid geometry desynchronization.

3. **Zone 3 Frame and Rail Treatments**:
   - Frames are rendered on Layer 0 with `CutFrame` (`BorderStyle=1`, `Outline=0`, `Shadow=0`), ensuring they sit behind all dialogue and headlines.
   - Rails are rendered on Layer 3 at `(res.rail_x, res.rail_y)` with `\fad(220,420)` and do not overlap dialogue.

4. **Zone 4 Safety & Responsiveness**:
   - Safe margins reserve >= 14% bottom canvas height. Dialogue anchored at `\an2` leaves > 300px clearance on 9:16 canvases, clearing TikTok/Reels/Shorts UI overlays.
   - Dynamic downscale limits font shrinking to a safe 58% minimum, preventing illegible or zero-sized text runs.

5. **FFmpeg Pipeline Cleanliness**:
   - Escaping colons (`\:`) and converting to POSIX forward slashes ensures compatibility across Windows path conventions in libass filters.
   - Complex filtergraphs (`fit_mode="blur"`) and simple filtergraphs (`fit_mode="letterbox"`, `fit_mode="crop"`) execute cleanly with zero warnings on stderr.

---

## 3. Caveats

- **libass Font Substitution**: Primary fonts (`Montserrat`, `Merriweather`, `JetBrains Mono`) reside in `backend/assets/fonts/`. In environments lacking these specific TTF files, libass falls back to system fonts (e.g. Arial). In the tested workspace, fonts are present and resolved cleanly.
- No other caveats.

---

## 4. Conclusion

**Verdict: APPROVE**

The multi-zone caption compilation and rendering pipeline meets all architectural, functional, and performance requirements specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`. It exhibits zero syntax warnings, robust edge-case handling, clean FFmpeg burn-in across all tested combinations, and 100% test pass status.

---

## 5. Verification Method

To independently verify this evaluation:

1. **Run Full Test Discovery**:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover tests/
   ```
   **Expected**: 72 tests pass with `OK`.

2. **Run Stderr Hygiene Audit Across All 18 Presets**:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import tempfile, subprocess
   from pathlib import Path
   from backend.captions.presets import PRESETS
   from backend.captions.ass import compile_ass
   from backend.app import EMOJI_MAP, extract_headline

   FONTS_DIR = Path('backend/assets/fonts').resolve().as_posix().replace(':', r'\:')
   words = [{'start': 0.0, 'end': 0.5, 'word': 'Test'}, {'start': 0.5, 'end': 1.0, 'word': 'Clean'}]
   with tempfile.TemporaryDirectory() as td:
       tdp = Path(td)
       for key, spec in PRESETS.items():
           ass_path = tdp / f'{key}.ass'
           out_mp4 = tdp / f'{key}.mp4'
           ass_content = compile_ass(spec, words=words, start=0.0, end=1.0, aspect='9:16')
           ass_path.write_text(ass_content, encoding='utf-8')
           cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30:duration=0.5', '-vf', f\"ass='{ass_path.resolve().as_posix().replace(':', r'\:')}':fontsdir='{FONTS_DIR}'\", '-c:v', 'libx264', '-preset', 'ultrafast', '-t', '0.5', str(out_mp4)]
           res = subprocess.run(cmd, capture_output=True, text=True)
           assert res.returncode == 0 and not res.stderr.strip(), f'Failed on {key}: {res.stderr}'
   print('ALL 18 PRESETS PRODUCED ZERO STDERR WARNINGS!')
   "
   ```
   **Expected**: Prints `ALL 18 PRESETS PRODUCED ZERO STDERR WARNINGS!`.

3. **Invalidation Conditions**:
   - Any test failure in `tests/test_cutflow.py`, `tests/test_e2e_features.py`, or `tests/test_adversarial_challenger.py`.
   - Any non-zero return code or warning output from FFmpeg libass filter during clip rendering.
