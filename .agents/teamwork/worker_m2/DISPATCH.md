# Dispatch: Worker M2 (Caption Styles Schema Mapping & KeyError Fix)

## Role
Implementation Worker for Milestone 2 (Caption Styles Schema Mapping and KeyError Fix across all 18 styles)

## Working Directory
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_m2

## Task
Read ORIGINAL_REQUEST.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md`

Read PROJECT.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md`

Read Survey Explorer 2 report at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_2\report.md`

## Write Ownership
You exclusively own:
- `backend/app.py` (lines 63-80: map CaptionSpec fields into `CAPTION_STYLES`; lines 1080-1120: defensive `.get()` lookups in `write_ass()`)
- `backend/captions/presets.py` (align `pulse` and `prime` accent colors)

## Requirements
1. In `backend/app.py:63-80`, map `CaptionSpec` fields into `CAPTION_STYLES`:
   - `base_color` = `spec.primary`
   - `outline_color` = `spec.outline`
   - `upcoming_color` = `spec.upcoming`
   - `back_color` = `spec.fill`
   - `show_headline` = `spec.headline != 'none'`
   - `badge_box` = `spec.caption_box == 'per_word' or spec.active == 'box'`
   - `pill` = `spec.caption_box == 'pill'`
   - `top_banner` = `spec.headline == 'banner'`
   - `vertical_side` = `bool(spec.rail)`
   - `outline` = `int(spec.outline_width * 4)`
   - `shadow` = `int(spec.shadow)`
   - `glow` = `int(spec.glow)`
   - `kinetic_pop` = `spec.active_pop`
2. In `backend/app.py` `write_ass()`, use defensive `.get()` lookups with fallbacks:
   - `base_color = style.get('base_color') or style.get('primary') or '&H00FFFFFF'`
   - `outline_color = style.get('outline_color') or style.get('outline') or '&H00111111'`
   - `accent_color = style.get('accent_color') or style.get('accent') or '&H00D5FF5F'`
   - `upcoming_color = style.get('upcoming_color') or style.get('upcoming') or '&H00999999'`
   - `back_color = style.get('back_color') or style.get('fill') or ('&H00FFFFFF' if is_badge_box else ('&H8A221832' if is_pill else '&H6A101010'))`
   Eliminate direct dictionary lookups `style["base_color"]`, `style["outline_color"]`, `style["accent_color"]` in lines 1084, 1087, 1098, 1099.
3. In `backend/captions/presets.py`:
   - `prime` preset: `accent="&H00FFFA93"`
   - `pulse` preset: `accent="&H0066F4C6"`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
Run baseline unit tests:
`.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_cutflow.py"`
Ensure all 31 baseline unit tests pass with 0 errors and 0 failures!
Document verification command and test output in your handoff report.
Write `handoff.md` and send a message when finished.


## 2026-10-30T21:53:51Z
You are Worker M2 for Cutflow.
Your working directory is:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_m2

Read ORIGINAL_REQUEST.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md

Read PROJECT.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md

Read DISPATCH.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_m2\DISPATCH.md

Read Survey Explorer 2 report at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_2\report.md

## Write Ownership
You exclusively own:
- backend/app.py (lines 63-80: map CaptionSpec fields into CAPTION_STYLES; lines 1080-1120: defensive .get() lookups in write_ass())
- backend/captions/presets.py (align pulse and prime accent colors)

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
Run tests:
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_cutflow.py"
Ensure all 31 baseline unit tests pass with 0 errors and 0 failures!
Document verification command and test output in your handoff report.
Write handoff.md and send a message when finished.
