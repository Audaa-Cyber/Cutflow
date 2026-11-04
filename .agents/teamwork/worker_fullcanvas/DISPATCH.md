## 2026-11-04T09:08:50Z
You are worker_fullcanvas, an implementation worker.
Your working directory is: c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_fullcanvas
Original request path: c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md

You MUST read c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md and the Project specification at c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md before starting work.

Read the detailed survey reports and recommendations from our explorers:
- c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_fc1\handoff.md
- c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_fc2\handoff.md
- c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\explorer_survey_fc3\handoff.md

FILE OWNERSHIP:
You exclusively own:
- backend/captions/ass.py
- backend/app.py

DO NOT modify files outside your ownership without justification.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TASKS TO IMPLEMENT:

1. In `backend/captions/ass.py`:
   - Fix underline double-offset bug (around line 648): change `pos=(left, y + h)` and `subrect(0, y, width, h)` to `pos=(left, y)` and `subrect(0, 0, width, h)` so active underlines render directly beneath words.
   - In `caption_events()` (around line 593): for `spec.caption_box == "per_word"`, ensure inter-token space is appended before `continue` so words do not get merged into a single word badge.
   - In `spec.bracket` indexing (around line 613): use `spec.bracket[-1]` instead of `spec.bracket[1]` so that the closing bracket `']'` is produced properly.
   - In `compile_ass(...)` (around line 677): change `if auto_headline and visible:` to `if auto_headline and (visible or candidate_text or headline_text):` so that fallback clips without dialogue words still render Zone 1 hook headline cards.
   - In `build_styles(res: Resolved)`: add compatibility style alias rows `Cutflow` (matching `Caption`) and `CutflowTitle` (matching `CutHeadline`) so that existing unit tests and legacy consumers pass seamlessly without regressions.

2. In `backend/app.py`:
   - Implement `resolve_caption_spec(caption_style, custom_style=None, uppercase=False, kinetic_pop=True) -> CaptionSpec`:
     - Resolve style key from `backend.captions.presets.PRESETS` (fallback to `PRESETS.get("clean")` or `PRESETS["focus"]`).
     - If `custom_style` dictionary is provided, translate legacy keys: `base_color` -> `primary`, `accent_color` -> `accent`, `outline_color` -> `outline`, `upcoming_color` -> `upcoming`, `back_color` -> `fill`, `badge_box` -> `caption_box="per_word", active="box"`, `pill` -> `caption_box="pill"`, `vertical_side` -> `rail="CUTFLOW // MOTION GRAPHICS"`, `top_banner` -> `headline="banner"`, `show_headline` -> `headline="none"` if False, `font` -> font family mapping, `glow`, `shadow`, etc., and apply via `spec.with_overrides(...)`.
     - Apply `uppercase` and `kinetic_pop` overrides if specified.
   - In `process_job()` (around line 1503): replace the legacy `write_ass(...)` call with:
     ```python
     spec = resolve_caption_spec(
         caption_style_to_use,
         custom_style=custom_style,
         uppercase=uppercase,
         kinetic_pop=job.get("kinetic_pop", True),
     )
     ass_content = ass_engine.compile_ass(
         spec,
         words=words_for_ass,
         start=candidate["start"],
         end=candidate["end"],
         aspect=job["aspect_ratio"],
         auto_emoji=auto_emoji,
         emoji_map=EMOJI_MAP,
         auto_headline=auto_headline_for_ass,
         candidate_text=candidate_text_for_ass,
         template=job["template"],
         extract_headline=extract_headline,
     )
     ass_path.write_text(ass_content, encoding="utf-8")
     ```
   - In `GET /api/jobs/{job_id}/clips/{filename}` (around line 1733): replace the legacy `write_ass(...)` call with the same `resolve_caption_spec(...)` + `ass_engine.compile_ass(...)` and `path.write_text(ass_content, encoding="utf-8")`.
   - Refactor `write_ass(...)` in `backend/app.py` to delegate to `resolve_caption_spec(...)` + `ass_engine.compile_ass(...)` + `path.write_text(ass_content, encoding="utf-8")` for backward compatibility.

3. Testing and Verification:
   - Run the test suite using the project virtual environment: `.\.venv\Scripts\python.exe -m unittest discover tests/`.
   - Verify all 63 unit tests pass with 0 failures and 0 errors.
   - Verify FFmpeg burns ASS subtitles across all caption styles cleanly.

4. Handoff:
   - Write your complete handoff report to `c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\worker_fullcanvas\handoff.md` following the Handoff Protocol (Observation, Logic Chain, Caveats, Conclusion, Verification Method).
   - Send a message to the orchestrator when completed.
