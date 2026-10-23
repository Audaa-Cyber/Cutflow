# Captions.ai Research for Cutflow

**Date:** 2026-10-24  
**Purpose:** Identify proven product and editing-workflow ideas that can improve Cutflow's existing video-to-highlights workflow.  
**Scope guard:** Cutflow remains a tool for importing existing videos, finding highlights, adding captions, and exporting clips. This research does not recommend turning Cutflow into a generative video, avatar, B-roll, music, or full multitrack-editing product.

## Research method and confidence

This is a **preliminary public-source product review** based on Captions' official feature pages and help documentation. It is not a completed REA runtime/code investigation. REA was not run against Captions in this environment because no authorized local Desktop Commander device is connected, and no Captions application bundle or browser runtime session was available to inspect. Treat the observations below as documented product behavior, not claims about Captions' internal implementation. A REA follow-up should collect evidence from an authorized browser/runtime session where possible.

## Findings from official sources

### 1. Caption controls are granular, not just preset-based

Captions documents controls for text, emphasis and active-word colors; active-word backgrounds; caption backgrounds, padding and corner radius; stroke and shadow; font, alignment, spacing and line height; words per line; lines per page; and caption transitions. It also supports emphasis effects and optional emoji behavior.  
Source: [Captions caption styles documentation](https://help.captions.ai/docs/captions/styles)

**What Cutflow can take from this**
- Keep presets simple, but expose a small set of useful per-style controls: primary text color, active-word color, outline/shadow, background, font size, and vertical position.
- Make line length and safe margins intentional. Short phrases and consistent sizing are more useful than forcing every caption into the same fixed word count.
- Preserve sensible defaults; do not expose every possible control at once.

### 2. Active-word timing and direct correction matter

Captions' guide describes tapping a word to correct its text and adjusting caption timing in the timeline. It also documents highlighting the active word as speech progresses. Captions are burned into the exported video.  
Sources: [Add captions guide](https://captions.ai/help/guides/creators/add-captions), [caption styles documentation](https://help.captions.ai/docs/captions/styles)

**What Cutflow can take from this**
- Word-level timestamps should be treated as a core rendering input, not just transcription metadata.
- Prioritize timing accuracy and readability before adding more flashy effects.
- A future correction workflow could let users fix transcription text or timing for a selected clip without reprocessing the entire source video. This is a product recommendation, not an existing Cutflow capability.

### 3. Styles are chosen for content context, with previews before commitment

Captions recommends different visual treatments for educational/talking-head, motivational, entertainment, professional, lifestyle, and advertising content. Its style guide encourages previewing a style on the actual footage and testing with a short sample before processing a longer clip.  
Sources: [Choosing a caption style](https://captions.ai/help/guides/engagement/choosing-a-style), [AI Edit style guide](https://captions.ai/help/guides/advanced/ai-edit-styles)

**What Cutflow can take from this**
- Keep Clean, Pulse, and Glow as distinct starting points, but describe their intended use in plain language.
- Where feasible, preview caption styles on a representative frame or a short sample before full rendering.
- Add a lightweight sample-render path only if it does not add disproportionate processing complexity.

### 4. Saved templates reduce repeated setup

Captions lets users customize a style and save it as a reusable template. Its guidance suggests keeping consistent styles for different publishing contexts.  
Source: [Choosing a caption style](https://captions.ai/help/guides/engagement/choosing-a-style)

**What Cutflow can take from this**
- Consider remembering the user's last-used caption preset and settings.
- Later, consider named custom presets only if users repeatedly request the same branding. This is a lower priority than ensuring current presets render correctly.

### 5. Targeted changes are better than restarting the entire edit

Captions' Co-editor documentation describes requesting specific changes in natural language and refining individual shots rather than regenerating the entire result. It also advises making requests specific.  
Source: [Edit without touching a timeline](https://captions.ai/help/guides/edit-faster/no-timeline-edit)

**What Cutflow can take from this**
- Prefer reusable, isolated render steps so changing caption styling or export resolution does not trigger transcription and highlight detection again.
- Cache derived outputs when safe, and invalidate only the artifacts affected by a setting change.
- Do not add a chat editor just because Captions has one; the transferable lesson is targeted rework, not the interface itself.

### 6. Export quality is an explicit end-of-workflow choice

Captions' workflow documentation puts resolution selection at export and recommends 1080p for most publishing platforms.  
Source: [Raw footage to finished video](https://captions.ai/help/guides/creators/ai-edit-workflow)

**What Cutflow can take from this**
- The new 480p, 720p, 1080p, and 2K controls fit a recognizable export workflow.
- Verify that the chosen resolution is visible near each clip's download action, that the downloaded file matches the selected dimensions, and that users understand 2K may be an upscale when the master is only 1080p.
- Keep the original master unchanged and generate alternate resolutions on demand.

### 7. AI Edit's broader scope is not a fit for Cutflow's current product boundary

Captions' AI Edit can combine a style with captions, transitions, B-roll, music, sound effects, and motion graphics. The official workflow recommends short, vertical, single-speaker source footage for best results, with limits varying across documentation and surfaces.  
Sources: [AI Edit feature page](https://captions.ai/features/edit-with-ai), [AI Edit documentation](https://help.captions.ai/docs/project/ai-edit), [creator workflow guide](https://captions.ai/help/guides/creators/ai-edit-workflow)

**What Cutflow should do**
- Learn from the workflow clarity, style previews, caption controls, and selective reprocessing.
- Do not add generated B-roll, generated music, avatars, or full AI scene generation as part of this research. Those are outside Cutflow's defined purpose.

## Recommended priorities for Cutflow

| Priority | Recommendation | Why | Acceptance check |
|---|---|---|---|
| P0 | Test real exports for all four resolutions and all three caption styles | Current automated tests do not prove visual quality or real FFmpeg behavior | Real MP4s play, dimensions match, audio is intact, captions stay within safe margins |
| P0 | Benchmark processing on the same representative source videos | The recent changes aim to improve speed, but speedup has not been measured | Record before/after total time and per-stage time |
| P1 | Improve active-word timing and phrase breaks | Caption readability depends on timing and natural grouping | Review a sample with fast speech, pauses, and long phrases |
| P1 | Preview styles on actual footage before full processing | Style quality depends on background and framing | User can compare styles on a short sample or representative frame |
| P1 | Cache and invalidate processing stages selectively | Avoid rerunning transcription/highlight detection for a caption/export-only change | Change export resolution without repeating transcription or highlight selection |
| P2 | Remember preferred caption settings | Reduces repetitive setup for recurring creators | Next project can reuse the previous selection, with a clear way to change it |
| P2 | Add manual correction of caption text/timing | Lets users repair names and transcription mistakes | Correction changes only the affected clip's render |

## REA follow-up: evidence still needed

The next REA pass should investigate observable behavior rather than guess at proprietary internals:

1. Inspect the public Captions web app in an authorized browser session and record the actual user-visible flow from import to captions to export.
2. Compare a few caption styles on the same source clip, noting phrase length, active-word behavior, safe margins, animation, and legibility over changing backgrounds.
3. Observe whether caption/style changes trigger full processing or only a targeted rerender, where this can be established from runtime evidence.
4. Capture the exact export options and verify which are available on the web surface and account tier being tested.
5. Separate confirmed observations from hypotheses. Do not infer backend architecture from UI behavior alone, and do not attempt to access private APIs, bypass authentication, or copy proprietary source/assets.

## Sources

- [Captions AI Edit](https://captions.ai/features/edit-with-ai)
- [Captions caption styles documentation](https://help.captions.ai/docs/captions/styles)
- [Add captions guide](https://captions.ai/help/guides/creators/add-captions)
- [Choosing a caption style](https://captions.ai/help/guides/engagement/choosing-a-style)
- [AI Edit style guide](https://captions.ai/help/guides/advanced/ai-edit-styles)
- [Edit without touching a timeline](https://captions.ai/help/guides/edit-faster/no-timeline-edit)
- [Raw footage to finished video](https://captions.ai/help/guides/creators/ai-edit-workflow)
