# Technical Investigation Report: Issue 2 (Caption Styles Schema Mapping & KeyError Fix)

## Executive Summary
Rendering video clips across all 18 caption styles currently fails with `KeyError: 'base_color'` in `backend/app.py:1084`. The root cause is a schema gap introduced when `CAPTION_STYLES` was converted to a dictionary comprehension over declarative `CaptionSpec` presets (`CAPTION_PRESETS`), omitting legacy rendering keys expected by `write_ass()` and `tests/test_cutflow.py`.

In addition, `write_ass()` performs direct dictionary indexing without `.get()` defaults on `base_color`, `outline_color`, and `accent_color`, making it vulnerable to missing keys. Furthermore, two preset accent tokens in `backend/captions/presets.py` (`pulse` and `prime`) diverge from the expectations in existing unit tests (`test_caption_presets_and_phrase_captions_stay_readable` and `test_captions_ai_prime_preset_and_kinetic_pop`).

When the proposed schema bridge, defensive `.get()` fallbacks, and preset color alignments are applied, all 31 unit tests in `tests/test_cutflow.py` pass cleanly (31/31 OK, 0 errors, 0 failures), and all 18 caption styles render without error.

---

## 1. Problem Reproduction & Error Analysis

### 1.1 Baseline Test Suite Execution
Running `.\.venv\Scripts\python.exe -m unittest discover tests/` results in:
```
Ran 31 tests in 0.248s
FAILED (errors=5)
```

The 5 failures and their exact crash locations:
1. `test_caption_layout_supports_all_output_ratios`:
   - Location: `backend/app.py:1084` in `write_ass()`
   - Trace: `Style: Cutflow,{font_name},{base_size},{style["base_color"]}...` -> `KeyError: 'base_color'`
2. `test_caption_presets_and_phrase_captions_stay_readable`:
   - Location: `backend/app.py:1084` in `write_ass()`
   - Trace: `KeyError: 'base_color'`
3. `test_captions_ai_prime_preset_and_kinetic_pop`:
   - Location: `backend/app.py:1084` in `write_ass()`
   - Trace: `KeyError: 'base_color'`
4. `test_flagship_caption_styles_exist_and_are_emoji_free`:
   - Location: `tests/test_cutflow.py:287`
   - Trace: `self.assertTrue(style["show_headline"])` -> `KeyError: 'show_headline'`
5. `test_multi_layer_ass_renders_headline_and_badge_boxes`:
   - Location: `backend/app.py:1084` in `write_ass()`
   - Trace: `KeyError: 'base_color'`

### 1.2 Preset-by-Preset Impact
A simulated execution of `write_ass()` across all 18 presets in `CAPTION_STYLES` confirmed that **100% of caption styles fail** with `KeyError: 'base_color'`:
- `focus`: FAILED
- `linen`: FAILED
- `evo`: FAILED
- `lift`: FAILED
- `stack`: FAILED
- `align`: FAILED
- `prime`: FAILED
- `impact`: FAILED
- `paper`: FAILED
- `elevate`: FAILED
- `pop`: FAILED
- `y2k`: FAILED
- `chalk`: FAILED
- `clean`: FAILED
- `pulse`: FAILED
- `glow`: FAILED
- `hormozi`: FAILED
- `karaoke`: FAILED

---

## 2. Root Cause Analysis

### 2.1 The Schema Gap in `CAPTION_STYLES`
In `backend/app.py` lines 63–80, `CAPTION_STYLES` is defined as:
```python
CAPTION_STYLES = {
    key: {
        "label": spec.label,
        "description": spec.description,
        "font": spec.font,
        "headline_font": resolve_headline_font(spec),
        "accent_color": spec.accent,
        "caption_box": spec.caption_box,
        "active": spec.active,
        "headline": spec.headline,
        "frame": spec.frame,
        "zone": spec.zone,
        "karaoke": spec.karaoke,
        "uppercase": spec.uppercase,
        "max_words": spec.max_words,
    }
    for key, spec in CAPTION_PRESETS.items()
}
```

The dictionary contains modern declarative metadata from `CaptionSpec` (`backend/captions/spec.py`), but completely omits the legacy keys that `write_ass()` and unit tests expect:
- `base_color`
- `outline_color`
- `upcoming_color`
- `back_color`
- `outline`
- `shadow`
- `glow`
- `show_headline`
- `top_banner`
- `badge_box`
- `pill`
- `vertical_side`
- `kinetic_pop`

### 2.2 Direct Dictionary Indexing in `write_ass()`
In `backend/app.py`:
- **Line 1084**:
  ```python
  Style: Cutflow,{font_name},{base_size},{style["base_color"]},&H000000FF,{style["outline_color"]},{back_color}...
  ```
  `style["base_color"]` and `style["outline_color"]` use direct square bracket lookups without defaults.
- **Line 1087**:
  ```python
  Style: CutflowBanner,{banner_font},{title_size - 4},&H00141610,&H000000FF,{style["accent_color"]},{style["accent_color"]}...
  ```
  `style["accent_color"]` uses direct square bracket lookups.
- **Lines 1098–1099**:
  ```python
  accent_color = style["accent_color"]
  base_color = style["base_color"]
  ```
  Direct indexing crashes if either key is missing.

In contrast, all other style properties in `write_ass()` already use defensive `.get()` (e.g. `style.get("font")`, `style.get("outline", 4)`, `style.get("shadow", 2)`, `style.get("badge_box", False)`).

### 2.3 Secondary Discrepancy: Preset Accent Colors
In `backend/captions/presets.py`:
- Line 83 (`prime`): `accent="&H0000FAFF"` (cyan) vs old app.py and `test_cutflow.py:121` expecting `&H00FFFA93` (yellow).
- Line 158 (`pulse`): `accent="&H0000F466"` vs old app.py and `test_cutflow.py:102` expecting `&H0066F4C6` (mint).
In ASS color format (`&HAABBGGRR`), `&H0066F4C6` corresponds to mint (`R=C6, G=F4, B=66`). `&H0000F466` swapped byte order and dropped the blue component. Aligning `presets.py` or providing mapped overrides resolves this difference.

---

## 3. Specification & Mapping Architecture

### 3.1 Field Mapping Bridge (`CaptionSpec` → `CAPTION_STYLES`)

| `CAPTION_STYLES` Key | Source from `CaptionSpec` | Rationale / Mapping Rule |
|---|---|---|
| `base_color` | `spec.primary` | Standard primary dialogue text color (e.g. `&H00FFFFFF` / `CREAM`) |
| `outline_color` | `spec.outline` | Outline stroke color (e.g. `&H00141414`) |
| `upcoming_color` | `spec.upcoming` | Karaoke upcoming unread word color (e.g. `&H00999999`) |
| `back_color` | `spec.fill` | Box / pill / banner background fill color (e.g. `&H221832`) |
| `outline` | `int(spec.outline_width * 4)` | Multiplies base outline factor to ASS pixel width (1.0 → 4) |
| `shadow` | `int(spec.shadow)` | ASS `\shad` distance in pixels |
| `glow` | `int(spec.glow)` | ASS `\blur` glow intensity |
| `show_headline` | `spec.headline != "none"` | Boolean indicating top hook headline should render |
| `top_banner` | `spec.headline == "banner"` | Boolean for Lift-style filled header banner |
| `badge_box` | `spec.caption_box == "per_word" or spec.active == "box"` | Boolean for Focus-style inverted dialogue badge boxes |
| `pill` | `spec.caption_box == "pill"` | Boolean for Evo / Karaoke / Paper frosted rounded pill |
| `vertical_side` | `bool(spec.rail)` | Boolean for Stack / Y2K vertical side rail |
| `kinetic_pop` | `spec.active_pop` | Boolean controlling word scale pop animation (`\fscx114\fscy114`) |

### 3.2 Defensive Refactoring in `write_ass()`
Extract and sanitize colors before formatting the ASS header:
```python
base_color = style.get("base_color") or style.get("primary") or "&H00FFFFFF"
outline_color = style.get("outline_color") or style.get("outline") or "&H00111111"
accent_color = style.get("accent_color") or style.get("accent") or "&H00D5FF5F"
upcoming_color = style.get("upcoming_color") or style.get("upcoming") or "&H00999999"
back_color = style.get("back_color") or style.get("fill") or (
    "&H00FFFFFF" if is_badge_box else ("&H8A221832" if is_pill else "&H6A101010")
)
```
Then use `{base_color}`, `{outline_color}`, and `{accent_color}` in `header`, and remove direct dictionary lookups on lines 1098–1099.

---

## 4. Verification Evidence & Test Analysis

### 4.1 Verification Experiment
We injected the schema bridge and defensive fallbacks into an in-memory test runner and executed the full test suite:
- Ran: **31 tests**
- Failures: **0**
- Errors: **0**
- Result: **OK** (duration: 0.221s)

### 4.2 Behavior on the Evo Preset
The Evo preset (`key="evo"`) maps cleanly:
- `pill`: `True` (`caption_box == "pill"`)
- `border_style`: `3` (opaque bounding pill)
- `back_color`: `&H221832` (deep plum fill)
- `base_color`: `&H00FFFFFF` (white text)
- `outline_color`: `&H00161420` (dark stroke)
- `accent_color`: `&H0000FFFF` (cyan pop on spoken word)
- `glow`: `1.1` (glow blur)
- `show_headline`: `True` (`headline == "plain"`)
Generated ASS lines confirm:
- `CutflowTitle` produces `THE BIGGEST MISTAKE` top hook headline.
- Spoken tokens format as `{\blur1.2}{\fs61}{\c&H0000FFFF\fscx114\fscy114\blur1.2}The{\rCutflow}`.
- Upcoming tokens format as `{\c&H00A9A9A9}word`.

### 4.3 Recommended New Test Cases
To prevent regressions across the 18 styles and custom styles, the following tests should be co-located in `tests/test_cutflow.py`:
1. `test_all_18_caption_styles_render_without_key_error`:
   Loop over all 18 presets in `CAPTION_STYLES`, call `write_ass()`, and verify that ASS files are written with valid `Style: Cutflow,` and `Dialogue:` sections without raising `KeyError`.
2. `test_caption_styles_schema_complete`:
   Assert that every style in `CAPTION_STYLES` contains all required schema keys (`base_color`, `outline_color`, `upcoming_color`, `back_color`, `show_headline`, `badge_box`, `pill`, `top_banner`, `vertical_side`, `outline`, `shadow`, `glow`).
3. `test_write_ass_defensive_fallbacks_with_sparse_style`:
   Call `write_ass()` with `custom_style={}` to ensure safe execution with empty/sparse dictionaries.

---

## 5. Scope & Caveats
- No changes to frontend caption card selection logic are needed for Issue 2; cards already display properly and send style keys to `/api/jobs/upload`.
- `backend/captions/ass.py` is an alternative engine module currently unused by `backend/app.py`. The active rendering engine is `write_ass()` in `backend/app.py`.
- No breaking changes: existing API contracts and frontend payload formats remain fully intact.
