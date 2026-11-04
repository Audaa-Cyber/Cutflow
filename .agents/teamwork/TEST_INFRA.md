# Test Infrastructure: Cutflow Automated Test Suite

## 1. Overview & Architecture

Cutflow automated testing infrastructure is built upon Python's standard `unittest` framework, requiring no external test runner dependencies. It is structured into two complementary test suites:

1. **`tests/test_cutflow.py`**:
   - 31 unit tests covering baseline MVP features: templates, candidate ranking, styling profiles, quality exports, prompt editing fallbacks, SQLite persistence, and initial caption styling.
2. **`tests/test_e2e_features.py`**:
   - 32 comprehensive tests (with 18 subtests covering each caption style) specifically targeting production fixes across 4 tiers:
     - **Tier 1 (Feature Coverage)**: R1 (Canvas Framing Default / F1–F3), R2 (Caption Styles Schema & Rendering / F4–F6), R3 (Bulk Deletion & History Cleanup / F7–F9).
     - **Tier 2 (Boundary, Corner & Adversarial Cases)**: Zero-job bulk deletion, missing/empty disk subdirectories, sparse/empty `custom_style` dictionaries in `write_ass()`, `None` color values, invalid `fit_mode` fallbacks, unescaped ASS meta-characters, empty words lists, invalid input combination validation.
     - **Tier 3 (Cross-Feature Combinations)**: Evo preset + Canvas framing rendering pipeline, multi-fit_mode job creation followed by bulk deletion, process cancellation & concurrency resurrection prevention.
     - **Tier 4 (Real-World Workflows)**: End-to-end video pipeline lifecycle simulation (creation -> ranking -> subtitle generation -> canvas framing render -> persistence -> deletion), prompt designer chip workflow, and multi-resolution variant exports.

---

## 2. Test Execution Commands

### Full Test Suite Discovery (Baseline + E2E)
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests/
```

### Dedicated E2E Feature Suite
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_e2e_features.py
```

### Targeted Tier-by-Tier Execution
```powershell
# Tier 1 - Canvas Framing Default
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1CanvasFramingDefault

# Tier 1 - Caption Styles Schema & Rendering
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1CaptionStylesSchemaAndRendering

# Tier 1 - Bulk Job Deletion
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier1BulkJobDeletion

# Tier 2 - Boundary & Adversarial Cases
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier2BoundaryAndCornerCases

# Tier 3 - Cross-Feature Combinations
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier3CrossFeatureCombinations

# Tier 4 - Real-World Workflows
.\.venv\Scripts\python.exe -m unittest tests.test_e2e_features.TestTier4RealWorldWorkflows
```

---

## 3. Test Isolation & Environment Design

Each test case adheres to strict test independence:
- **Temporary Directories**: All file outputs (`.ass` subtitle files, `.mp4` export clips, temporary uploads/outputs) use `tempfile.TemporaryDirectory()`.
- **In-Memory State Isolation**: `TestTier1BulkJobDeletion`, `TestTier2BoundaryAndCornerCases`, `TestTier3CrossFeatureCombinations`, and `TestTier4RealWorldWorkflows` save and restore `JOBS`, `ACTIVE_PROCESSES`, and `CANCELLED_JOBS` inside `setUp` and `tearDown` blocks under `LOCK`.
- **Database Isolation**: The test runner utilizes `CUTFLOW_DB_PATH` in a dedicated test SQLite file, ensuring tests do not corrupt development database records.
- **Process & Network Mocking**: Background worker submissions via `POOL.submit` and FFmpeg shell commands via `run_command` are patched using `unittest.mock.patch` to execute instantaneously without requiring active GPU/CPU video encoding.

---

## 4. Test Matrix & Requirement Mapping

| Tier | Test Class | Test Case | Target Requirement | Key Assertion |
|---|---|---|---|---|
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_render_clip_signature_default_fit_mode_is_blur` | R1 / F3 | `fit_mode` parameter default is `"blur"` |
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_render_clip_omitted_fit_mode_executes_ambient_blur_filter` | R1 / F3 | FFmpeg `-filter_complex` with `boxblur=28:5` |
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_create_job_default_fit_mode_is_blur` | R1 / F3 | `job["fit_mode"] == "blur"` |
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_url_job_schema_default_fit_mode_is_blur` | R1 / F3 | `URLJob.model_fields["fit_mode"].default == "blur"` |
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_frontend_html_canvas_framing_default_state_and_labels` | R1 / F1 | `.fit-mode-btn.selected` is blur; labels match spec |
| **Tier 1** | `TestTier1CanvasFramingDefault` | `test_frontend_js_state_and_settings_framing_default` | R1 / F2 | `fitMode: "blur"`, `aria-checked` synced |
| **Tier 1** | `TestTier1CaptionStylesSchemaAndRendering` | `test_all_18_caption_styles_present` | R2 / F4 | All 18 preset keys present in `CAPTION_STYLES` |
| **Tier 1** | `TestTier1CaptionStylesSchemaAndRendering` | `test_caption_styles_schema_keys_present_across_all_18_styles` | R2 / F4 | 13 mapped schema bridge keys present in all 18 styles |
| **Tier 1** | `TestTier1CaptionStylesSchemaAndRendering` | `test_all_18_caption_styles_render_ass_without_error` | R2 / F4, F5 | `write_ass()` renders each of the 18 styles without KeyError |
| **Tier 1** | `TestTier1CaptionStylesSchemaAndRendering` | `test_preset_accent_color_alignment_pulse_and_prime` | R2 / F6 | Pulse accent is mint, Prime accent is yellow |
| **Tier 1** | `TestTier1CaptionStylesSchemaAndRendering` | `test_flagship_specific_layout_attributes` | R2 / F4 | Evo pill=True, Focus badge_box=True, Lift banner=True |
| **Tier 1** | `TestTier1BulkJobDeletion` | `test_bulk_delete_route_registered_on_app` | R3 / F8 | `DELETE /api/jobs` registered in `app.routes` |
| **Tier 1** | `TestTier1BulkJobDeletion` | `test_bulk_delete_clears_memory_database_and_disk` | R3 / F8 | Memory, SQLite, and upload/output folders purged |
| **Tier 1** | `TestTier1BulkJobDeletion` | `test_bulk_delete_kills_active_processes_and_cancels` | R3 / F8 | `proc.kill()` called, job in `CANCELLED_JOBS` |
| **Tier 1** | `TestTier1BulkJobDeletion` | `test_frontend_html_delete_all_button_rendered` | R3 / F9 | `#delete-all-projects-button.danger-button` exists |
| **Tier 1** | `TestTier1BulkJobDeletion` | `test_frontend_js_delete_all_projects_function` | R3 / F9 | `deleteAllProjects()` sends DELETE and resets UI state |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_bulk_delete_with_zero_jobs_returns_cleanly` | R3 Boundary | Returns `{"ok": True, "deleted_count": 0}` |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_bulk_delete_handles_missing_or_empty_disk_dirs` | R3 Boundary | Handles loose files or missing dirs without crash |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_write_ass_with_sparse_custom_style_defensive_fallbacks` | R2 Boundary | Defensive `.get()` fallbacks for empty/sparse custom styles |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_write_ass_with_none_or_missing_color_keys` | R2 Boundary | None color values safely fallback to defaults |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_write_ass_with_invalid_style_key_fallback` | R2 Boundary | Unknown style key falls back cleanly |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_create_job_invalid_fit_mode_falls_back_to_blur` | R1 Boundary | Unrecognized fit_mode normalizes to `"blur"` |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_render_clip_invalid_fit_mode_falls_back_to_blur` | R1 Boundary | Unrecognized fit_mode renders ambient blur |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_write_ass_handles_empty_words_gracefully` | Adversarial | Empty words list does not crash `write_ass()` |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_write_ass_escaping_and_special_characters` | Adversarial | Meta-characters, braces, backslashes, emojis sanitized |
| **Tier 2** | `TestTier2BoundaryAndCornerCases` | `test_create_job_invalid_input_combinations_rejected` | Adversarial | Invalid duration, clip count, aspect ratio raise 400 |
| **Tier 3** | `TestTier3CrossFeatureCombinations` | `test_evo_preset_with_default_canvas_framing` | Combination R1+R2 | Evo preset combined with Canvas Framing render filtergraph |
| **Tier 3** | `TestTier3CrossFeatureCombinations` | `test_job_lifecycle_multiple_fit_modes_then_bulk_delete` | Combination R1+R3 | Multiple jobs with different framing bulk-deleted |
| **Tier 3** | `TestTier3CrossFeatureCombinations` | `test_bulk_delete_during_in_flight_worker_prevents_reinsertion` | Combination R3 Concurrency | Post-deletion worker `update_job` does not resurrect job |
| **Tier 4** | `TestTier4RealWorldWorkflows` | `test_e2e_full_job_pipeline_lifecycle` | Workflow Lifecycle | Full lifecycle: Create -> Rank -> Subtitle -> Render -> Delete |
| **Tier 4** | `TestTier4RealWorldWorkflows` | `test_prompt_designer_evo_chip_workflow` | Workflow Chips | "Evo Frosted Pill" prompt chip parsed and rendered |
| **Tier 4** | `TestTier4RealWorldWorkflows` | `test_multi_resolution_export_workflow` | Workflow Exports | Multi-resolution Lanczos scaling across 720, 1080, 2k |
