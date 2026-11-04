# Project: Captions.ai Full-Canvas Captioning Implementation

## Architecture
Cutflow is an automated short-form video clipping platform with a FastAPI backend (`backend/app.py`), full-canvas multi-zone caption compilation engine (`backend/captions/`), vanilla JS frontend, SQLite persistence (`data/cutflow.sqlite3`), and an FFmpeg rendering pipeline.

- **Caption Compilation Engine (`backend/captions/`)**:
  - `spec.py`: Declarative `CaptionSpec` dataclass defining typography, colors, geometry, box decorations, headlines, frames, and rails.
  - `presets.py`: 18 production preset definitions (`PRESETS`) covering flagship, viral kinetic, and creator caption styles.
  - `ass.py`: `compile_ass()` compiler transforming words, transcript, and `CaptionSpec` into ASS subtitles across 4 distinct canvas zones:
    - Zone 1: Hook Headline / Banner (Layer 2 `CutHeadline`, `CutBadgeHeadline`, Layer 3 emerald banner box)
    - Zone 2: Kinetic Dialogue (Layer 1 vector `\p1` rounded pills, marker highlights, underlines; Layer 4 karaoke color pop with punch `\fscx114\fscy114`)
    - Zone 3: Frame / Rails (Layer 0 vector frames: letterbox, polaroid border, 3x3 cyber grid crosshairs, CRT scanlines, rules; Layer 3 side rail text)
    - Zone 4: Safe Margins (lower 17% height cleared for mobile UI, dynamic downscaling to 58% for long dialogue runs)
- **Backend Rendering Pipeline (`backend/app.py`)**:
  - `process_job()`: Resolves `CaptionSpec` from `PRESETS`, compiles multi-zone ASS via `compile_ass()`, writes to `.ass` file, and invokes `render_clip()` with FFmpeg native `ass` video filter.
  - `GET /api/jobs/{job_id}/clips/{filename}`: On-the-fly ASS compilation and download.
  - `write_ass()`: Compatibility facade delegating to `resolve_caption_spec()` + `compile_ass()`.
- **FFmpeg Integration**:
  - Burns compiled multi-zone ASS scripts into candidate clips via `ass='<escaped_path>':fontsdir='<escaped_fontsdir>'`.
  - Windows path escaping resolves forward slashes with `.as_posix()` and escapes drive colons with `\:`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Multi-Zone Layout Engine Bug Fixes & Compat | In `backend/captions/ass.py`, fix underline double-offset bug, add space between `per_word` badges, fix bracket indexing `spec.bracket[-1]`, support Zone 1 headlines on fallback clips with empty words, and include `Cutflow` & `CutflowTitle` alias rows in `build_styles()`. | M1 | Survey R1/R2 |
| F2 | Full-Canvas Caption Compilation Pipeline Integration | In `backend/app.py`, implement `resolve_caption_spec()` resolving styles from `PRESETS` with fallback & `custom_style` adapter. Update `process_job()` and clip download endpoints to call `compile_ass(...)` instead of legacy `write_ass()`, and make `write_ass()` delegate to `compile_ass()`. | M1 | Survey R1 |
| F3 | Multi-Zone Style Burning Verification across 18 styles | Verify all 18 caption styles (`focus`, `linen`, `evo`, `lift`, `prime`, `impact`, `paper`, `elevate`, `pop`, `y2k`, `chalk`, `clean`, `pulse`, `glow`, `hormozi`, `karaoke`, `stack`, `align`) compile and burn cleanly into candidate clips via FFmpeg without errors. | M2 | Survey R2/R3 |
| F4 | Comprehensive Unit Test Suite Verification | Verify `python -m unittest discover tests/` runs with zero failures and zero errors across all 63 unit tests. | M2 | Survey R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Full-Canvas Caption Compilation & Multi-Zone Layout Integration | F1, F2 (`backend/captions/ass.py`, `backend/app.py`) | none | DONE |
| M2 | Comprehensive Testing & FFmpeg Multi-Style Verification | F3, F4 (`tests/`, FFmpeg burn-in) | M1 | DONE |

## Interface Contracts
### Caption Spec Resolution & Compilation
- `resolve_caption_spec(caption_style, custom_style=None, uppercase=False, kinetic_pop=True) -> CaptionSpec`:
  - Returns `CaptionSpec` from `PRESETS[caption_style]` or fallback to `PRESETS["clean"]` / `PRESETS["focus"]`.
  - Maps `custom_style` dictionary keys to `CaptionSpec` fields (`base_color` -> `primary`, `accent_color` -> `accent`, `outline_color` -> `outline`, `upcoming_color` -> `upcoming`, `back_color` -> `fill`, `badge_box` -> `caption_box="per_word", active="box"`, `pill` -> `caption_box="pill"`, `vertical_side` -> `rail="CUTFLOW // MOTION GRAPHICS"`, `top_banner` -> `headline="banner"`, `show_headline` -> `headline="none"`).
- `compile_ass(spec, *, words, start, end, aspect, auto_emoji=False, emoji_map=None, auto_headline=True, headline_text=None, hook_duration=None, candidate_text="", template="podcast", extract_headline=None) -> str`:
  - Returns ASS script string containing `[Script Info]`, `[V4+ Styles]`, and layered `[Events]`.
- `write_ass(...)`:
  - Accepts legacy signature, delegates to `resolve_caption_spec` + `compile_ass(...)`, and writes output to `path`.

## Code Layout
- `backend/captions/ass.py`: Owned exclusively by M1 (layout bug fixes, fallback headline support, alias styles).
- `backend/app.py`: Owned exclusively by M1 (`resolve_caption_spec`, `process_job`, clip download endpoint, `write_ass` delegation).
- `tests/test_cutflow.py` & `tests/test_e2e_features.py`: Owned by M2 (verified without regression, test suite execution).
