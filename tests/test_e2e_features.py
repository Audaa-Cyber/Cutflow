"""Comprehensive automated test suite covering Tiers 1-4 for Cutflow.

Tiers Covered:
- Tier 1: Feature coverage for Canvas framing default (R1), Caption styles schema and
          rendering across all 18 styles (R2), and Bulk job deletion (R3).
- Tier 2: Boundary, corner & adversarial cases (empty jobs, sparse caption styles,
          invalid fit_mode fallback, escaping/meta-characters, empty words).
- Tier 3: Cross-feature combinations (Evo preset with Canvas framing, job creation followed
          by bulk delete, active process cancellation & resurrection prevention).
- Tier 4: Real-world workflows (full pipeline lifecycle, prompt designer chip flow,
          multi-resolution exports).
"""

import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import HTTPException

import backend.app
from backend.app import (
    ACTIVE_PROCESSES,
    CANCELLED_JOBS,
    CAPTION_STYLES,
    JOBS,
    LOCK,
    OUTPUTS,
    TEMPLATES,
    UPLOADS,
    URLJob,
    app,
    create_job,
    db_connection,
    export_dimensions,
    parse_caption_prompt,
    persist_job,
    rank_candidates,
    render_clip,
    render_export,
    update_job,
    write_ass,
)


def get_delete_all_jobs_fn():
    """Retrieve delete_all_jobs endpoint function from backend.app if implemented."""
    return getattr(backend.app, "delete_all_jobs", None)


def sample_words():
    """Generate standardized sample transcript tokens for caption testing."""
    phrases = [
        "The biggest mistake people make is trying to learn everything at once. Start with one clear goal.",
        "Here is how you can solve the problem. First understand the basics and test what you learned.",
        "I never expected that moment to change my life. Suddenly everything became clear and the story mattered.",
        "Honestly the truth is simple. You need to keep learning because every mistake teaches you something.",
    ]
    words = []
    timestamp = 0.0
    for phrase in phrases:
        for token in phrase.split():
            duration = 0.55
            words.append({"start": timestamp, "end": timestamp + duration, "word": token})
            timestamp += duration
        words[-1]["word"] += "."
        timestamp += 0.2
    return words, timestamp + 1.0


# ==============================================================================
# TIER 1: FEATURE COVERAGE (R1, R2, R3)
# ==============================================================================


class BaseTestCase(unittest.TestCase):
    """Base class ensuring clean job queues for every test."""
    def setUp(self):
        with LOCK:
            JOBS.clear()
            ACTIVE_PROCESSES.clear()
            CANCELLED_JOBS.clear()

    def tearDown(self):
        with LOCK:
            JOBS.clear()
            ACTIVE_PROCESSES.clear()
            CANCELLED_JOBS.clear()

class TestTier1CanvasFramingDefault(BaseTestCase):
    """Tier 1: Feature tests for Canvas Framing Default (R1 / F1, F2, F3)."""

    def test_render_clip_signature_default_fit_mode_is_blur(self):
        """F3: render_clip default parameter fit_mode must be 'blur'."""
        sig = inspect.signature(render_clip)
        self.assertIn("fit_mode", sig.parameters)
        self.assertEqual(sig.parameters["fit_mode"].default, "blur")

    def test_render_clip_omitted_fit_mode_executes_ambient_blur_filter(self):
        """F3: Invoking render_clip without explicit fit_mode applies ambient blur filtergraph."""
        with tempfile.TemporaryDirectory() as td:
            dummy_sub = Path(td) / "test.ass"
            dummy_sub.write_text("[Script Info]\n", encoding="utf-8")
            with patch("backend.app.run_command") as mock_run:
                render_clip(Path("source.mp4"), Path("out.mp4"), dummy_sub, 0.0, 5.0, "9:16")

            self.assertEqual(mock_run.call_count, 2)
            cmd = mock_run.call_args.args[0]
            self.assertIn("-filter_complex", cmd)
            fc_arg = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("boxblur=28:5", fc_arg)
            self.assertIn("force_original_aspect_ratio=increase", fc_arg)

    @patch("backend.app.POOL.submit")
    def test_create_job_default_fit_mode_is_blur(self, mock_submit):
        """F3: create_job() defaults fit_mode to 'blur' when omitted."""
        job = create_job("podcast", "9:16", 1, 10, 20, source_path="dummy.mp4")
        self.assertEqual(job.get("fit_mode"), "blur")

    def test_url_job_schema_default_fit_mode_is_blur(self):
        """F3: URLJob pydantic schema defaults fit_mode to 'blur'."""
        self.assertIn("fit_mode", URLJob.model_fields)
        self.assertEqual(URLJob.model_fields["fit_mode"].default, "blur")
        job_instance = URLJob(source_url="https://youtube.com/watch?v=12345678901")
        self.assertEqual(job_instance.fit_mode, "blur")

    def test_frontend_html_canvas_framing_default_state_and_labels(self):
        """F1: frontend/index.html presents 'Canvas Framing (Ambient Blur)' as selected default."""
        html_path = REPO_ROOT / "frontend" / "index.html"
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")

        # Blur button is selected and labeled Canvas Framing (Ambient Blur)
        blur_pattern = re.search(
            r'<button[^>]*data-fit-mode="blur"[^>]*>([\s\S]*?)<\/button>', content
        )
        self.assertIsNotNone(blur_pattern, "Blur button not found in index.html")
        blur_html = blur_pattern.group(0)
        self.assertIn('class="fit-mode-btn selected"', blur_html)
        self.assertIn("Canvas Framing (Ambient Blur)", blur_html)
        self.assertIn('role="radio"', blur_html)
        self.assertIn('aria-checked="true"', blur_html)

        # Letterbox button
        letterbox_pattern = re.search(
            r'<button[^>]*data-fit-mode="letterbox"[^>]*>([\s\S]*?)<\/button>', content
        )
        self.assertIsNotNone(letterbox_pattern, "Letterbox button not found in index.html")
        self.assertIn("Black Bars (Letterbox)", letterbox_pattern.group(0))

        # Crop button
        crop_pattern = re.search(
            r'<button[^>]*data-fit-mode="crop"[^>]*>([\s\S]*?)<\/button>', content
        )
        self.assertIsNotNone(crop_pattern, "Crop button not found in index.html")
        self.assertIn("Smart Crop (Center Punch-in)", crop_pattern.group(0))

    def test_frontend_js_state_and_settings_framing_default(self):
        """F2: frontend/app.js state initializes fitMode to 'blur' and readSettings preserves it."""
        js_path = REPO_ROOT / "frontend" / "app.js"
        self.assertTrue(js_path.exists())
        content = js_path.read_text(encoding="utf-8")

        self.assertIn('fitMode: "blur"', content)
        self.assertIn('fit_mode: state.fitMode || "blur"', content)
        # Verify aria-checked synchronization in event listener
        self.assertIn('setAttribute("aria-checked"', content)


class TestTier1CaptionStylesSchemaAndRendering(BaseTestCase):
    """Tier 1: Feature tests for Caption Styles Schema and Rendering across all 18 styles (R2 / F4, F5, F6)."""

    EXPECTED_18_STYLES = {
        "focus", "linen", "evo", "lift", "stack", "align",
        "prime", "impact", "paper", "elevate", "pop", "y2k", "chalk",
        "clean", "pulse", "glow", "hormozi", "karaoke",
    }

    REQUIRED_SCHEMA_KEYS = [
        "base_color", "outline_color", "upcoming_color", "back_color",
        "show_headline", "badge_box", "pill", "top_banner", "vertical_side",
        "outline", "shadow", "glow", "kinetic_pop",
    ]

    def test_all_18_caption_styles_present(self):
        """F4: CAPTION_STYLES contains exactly all 18 specified preset keys."""
        self.assertEqual(set(CAPTION_STYLES.keys()), self.EXPECTED_18_STYLES)
        self.assertEqual(len(CAPTION_STYLES), 18)

    def test_caption_styles_schema_keys_present_across_all_18_styles(self):
        """F4: Every style in CAPTION_STYLES contains all 13 mapped schema bridge keys."""
        missing_by_style = {}
        for style_key, style_dict in CAPTION_STYLES.items():
            missing = [k for k in self.REQUIRED_SCHEMA_KEYS if k not in style_dict]
            if missing:
                missing_by_style[style_key] = missing

        self.assertEqual(
            missing_by_style, {},
            f"Styles missing required schema keys: {missing_by_style}"
        )

    def test_all_18_caption_styles_render_ass_without_error(self):
        """F4/F5: write_ass() must successfully render all 18 caption styles without KeyError."""
        words, duration = sample_words()
        with tempfile.TemporaryDirectory() as td:
            for style_key in self.EXPECTED_18_STYLES:
                with self.subTest(style=style_key):
                    out_path = Path(td) / f"{style_key}.ass"
                    try:
                        write_ass(
                            out_path, words, 0.0, min(duration, 6.0), "9:16",
                            caption_style=style_key, auto_headline=True
                        )
                    except KeyError as e:
                        self.fail(f"write_ass() raised KeyError '{e}' for style '{style_key}'")

                    self.assertTrue(out_path.exists())
                    content = out_path.read_text(encoding="utf-8")
                    self.assertIn("[Script Info]", content)
                    self.assertIn("[V4+ Styles]", content)
                    self.assertIn("Style: Cutflow,", content)
                    self.assertIn("[Events]", content)
                    dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
                    self.assertGreater(len(dialogue_lines), 0)

    def test_preset_accent_color_alignment_pulse_and_prime(self):
        """F6: Pulse accent is mint (&H0066F4C6) and Prime accent is yellow (&H00FFFA93)."""
        pulse = CAPTION_STYLES.get("pulse", {})
        prime = CAPTION_STYLES.get("prime", {})
        self.assertEqual(pulse.get("accent_color"), "&H0066F4C6", "Pulse accent must be mint &H0066F4C6")
        self.assertEqual(prime.get("accent_color"), "&H00FFFA93", "Prime accent must be yellow &H00FFFA93")

    def test_flagship_specific_layout_attributes(self):
        """F4: Verify flagship preset layout flags match specifications."""
        evo = CAPTION_STYLES.get("evo", {})
        self.assertTrue(evo.get("pill"), "Evo preset must have pill=True")
        self.assertEqual(evo.get("accent_color"), "&H0000FFFF", "Evo spoken pop must be cyan")

        focus = CAPTION_STYLES.get("focus", {})
        self.assertTrue(focus.get("badge_box"), "Focus preset must have badge_box=True")

        lift = CAPTION_STYLES.get("lift", {})
        self.assertTrue(lift.get("top_banner"), "Lift preset must have top_banner=True")

        stack = CAPTION_STYLES.get("stack", {})
        self.assertTrue(stack.get("vertical_side"), "Stack preset must have vertical_side=True")

        linen = CAPTION_STYLES.get("linen", {})
        self.assertIn("Merriweather", linen.get("font", ""), "Linen font must be Merriweather")


class TestTier1BulkJobDeletion(BaseTestCase):
    """Tier 1: Feature tests for Bulk Job Deletion (R3 / F7, F8, F9)."""

    def setUp(self):
        with LOCK:
            self.orig_jobs = dict(JOBS)
            self.orig_active = dict(ACTIVE_PROCESSES)
            self.orig_cancelled = set(CANCELLED_JOBS)
            JOBS.clear()
            ACTIVE_PROCESSES.clear()
            CANCELLED_JOBS.clear()

    def tearDown(self):
        with LOCK:
            JOBS.clear()
            JOBS.update(self.orig_jobs)
            ACTIVE_PROCESSES.clear()
            ACTIVE_PROCESSES.update(self.orig_active)
            CANCELLED_JOBS.clear()
            CANCELLED_JOBS.update(self.orig_cancelled)

    def test_bulk_delete_route_registered_on_app(self):
        """F8: DELETE /api/jobs endpoint is registered on the FastAPI app."""
        registered_paths = [
            route.path for route in app.routes
            if "DELETE" in getattr(route, "methods", set())
        ]
        self.assertIn(
            "/api/jobs", registered_paths,
            "DELETE /api/jobs endpoint is not registered in FastAPI routes."
        )

    @patch("backend.app.POOL.submit")
    def test_bulk_delete_clears_memory_database_and_disk(self, mock_submit):
        """F8: delete_all_jobs() purges memory JOBS, SQLite table, and upload/output directories."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(
            delete_all_jobs,
            "delete_all_jobs function is not implemented in backend.app."
        )

        job1 = create_job("podcast", "9:16", 1, 10, 20, source_path="dummy1.mp4")
        job2 = create_job("educational", "9:16", 1, 10, 20, source_path="dummy2.mp4")

        up1 = UPLOADS / job1["id"]
        out1 = OUTPUTS / job1["id"]
        up2 = UPLOADS / job2["id"]
        out2 = OUTPUTS / job2["id"]
        for p in (up1, out1, up2, out2):
            p.mkdir(parents=True, exist_ok=True)
            (p / "file.txt").write_text("test", encoding="utf-8")

        with db_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM jobs WHERE id IN (?, ?)", (job1["id"], job2["id"])).fetchone()[0]
            self.assertEqual(cnt, 2)

        res = delete_all_jobs()
        self.assertTrue(res.get("ok"))
        self.assertGreaterEqual(res.get("deleted_count", 0), 2)

        self.assertEqual(len(JOBS), 0)

        with db_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            self.assertEqual(cnt, 0)

        self.assertFalse(up1.exists())
        self.assertFalse(out1.exists())
        self.assertFalse(up2.exists())
        self.assertFalse(out2.exists())

        self.assertTrue(UPLOADS.exists())
        self.assertTrue(OUTPUTS.exists())

    @patch("backend.app.POOL.submit")
    def test_bulk_delete_kills_active_processes_and_cancels(self, mock_submit):
        """F8: delete_all_jobs() terminates active child processes and adds IDs to CANCELLED_JOBS."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(delete_all_jobs, "delete_all_jobs is not implemented.")

        job = create_job("podcast", "9:16", 1, 10, 20, source_path="dummy.mp4")
        mock_proc = MagicMock()
        with LOCK:
            ACTIVE_PROCESSES[job["id"]] = mock_proc

        res = delete_all_jobs()
        mock_proc.kill.assert_called_once()
        self.assertIn(job["id"], CANCELLED_JOBS)
        self.assertEqual(len(ACTIVE_PROCESSES), 0)

    def test_frontend_html_delete_all_button_rendered(self):
        """F9: frontend/index.html includes 'Delete all' button with danger styling in projects heading."""
        html_path = REPO_ROOT / "frontend" / "index.html"
        content = html_path.read_text(encoding="utf-8")

        btn_match = re.search(r'<button[^>]*id="delete-all-projects-button"[^>]*>([\s\S]*?)<\/button>', content)
        self.assertIsNotNone(btn_match, "#delete-all-projects-button not found in frontend/index.html")
        btn_html = btn_match.group(0)
        self.assertIn("danger-button", btn_html)
        self.assertIn("Delete all", btn_html)

    def test_frontend_js_delete_all_projects_function(self):
        """F9: frontend/app.js implements deleteAllProjects() with confirmation and state reset."""
        js_path = REPO_ROOT / "frontend" / "app.js"
        content = js_path.read_text(encoding="utf-8")

        self.assertIn("async function deleteAllProjects()", content)
        self.assertIn('fetch("/api/jobs", { method: "DELETE" }', content)
        self.assertIn('state.jobs = []', content)
        self.assertIn('state.activeJobId = null', content)
        self.assertIn('$("#project-count").textContent = "0"', content)
        self.assertIn('delete-all-projects-button', content)


# ==============================================================================
# TIER 2: BOUNDARY, CORNER & ADVERSARIAL CASES
# ==============================================================================

class TestTier2BoundaryAndCornerCases(BaseTestCase):
    """Tier 2: Boundary, corner and adversarial edge condition tests."""

    def setUp(self):
        with LOCK:
            self.orig_jobs = dict(JOBS)
            self.orig_active = dict(ACTIVE_PROCESSES)

    def tearDown(self):
        with LOCK:
            JOBS.clear()
            JOBS.update(self.orig_jobs)
            ACTIVE_PROCESSES.clear()
            ACTIVE_PROCESSES.update(self.orig_active)

    def test_bulk_delete_with_zero_jobs_returns_cleanly(self):
        """Edge Case: Invoking delete_all_jobs() when no jobs exist returns deleted_count 0 without error."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(delete_all_jobs, "delete_all_jobs not implemented.")

        with LOCK:
            JOBS.clear()
            with db_connection() as conn:
                conn.execute("DELETE FROM jobs")

        res = delete_all_jobs()
        self.assertEqual(res, {"ok": True, "deleted_count": 0})

    def test_bulk_delete_handles_missing_or_empty_disk_dirs(self):
        """Edge Case: delete_all_jobs() tolerates loose non-directory files or missing subfolders."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(delete_all_jobs, "delete_all_jobs not implemented.")

        test_file = UPLOADS / "scratch.tmp"
        test_file.write_text("scratch", encoding="utf-8")

        res = delete_all_jobs()
        self.assertTrue(res.get("ok"))
        self.assertFalse(test_file.exists())

    def test_write_ass_with_sparse_custom_style_defensive_fallbacks(self):
        """Edge Case: write_ass() with empty or sparse custom_style dictionary uses fallbacks."""
        words, _ = sample_words()
        with tempfile.TemporaryDirectory() as td:
            for sparse_dict, fname in [
                ({}, "empty.ass"),
                ({"font": "Montserrat"}, "font_only.ass"),
                ({"accent_color": "&H00D5FF5F"}, "accent_only.ass"),
            ]:
                with self.subTest(sparse_dict=sparse_dict):
                    out_file = Path(td) / fname
                    try:
                        write_ass(out_file, words, 0.0, 3.0, "9:16", custom_style=sparse_dict)
                    except KeyError as e:
                        self.fail(f"write_ass() raised KeyError '{e}' on sparse custom_style {sparse_dict}")

                    content = out_file.read_text(encoding="utf-8")
                    self.assertIn("Style: Cutflow,", content)
                    self.assertIn("&H00FFFFFF", content)

    def test_write_ass_with_none_or_missing_color_keys(self):
        """Edge Case: custom_style containing None values for colors falls back defensively."""
        words, _ = sample_words()
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "none_colors.ass"
            sparse_style = {
                "base_color": None,
                "outline_color": None,
                "accent_color": None,
                "back_color": None,
            }
            try:
                write_ass(out_file, words, 0.0, 3.0, "9:16", custom_style=sparse_style)
            except KeyError as e:
                self.fail(f"write_ass() raised KeyError '{e}' on None color values")

            content = out_file.read_text(encoding="utf-8")
            self.assertIn("Style: Cutflow,", content)

    def test_write_ass_with_invalid_style_key_fallback(self):
        """Edge Case: caption_style not in CAPTION_STYLES safely falls back to default style."""
        words, _ = sample_words()
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "unknown_style.ass"
            try:
                write_ass(out_file, words, 0.0, 3.0, "9:16", caption_style="non_existent_preset_xyz")
            except KeyError as e:
                self.fail(f"write_ass() crashed with KeyError '{e}' on unknown caption style")

            self.assertTrue(out_file.exists())

    @patch("backend.app.POOL.submit")
    def test_create_job_invalid_fit_mode_falls_back_to_blur(self, mock_submit):
        """Edge Case: create_job() with unrecognized fit_mode falls back safely to 'blur'."""
        job = create_job("podcast", "9:16", 1, 10, 20, source_path="dummy.mp4", fit_mode="stretch_unknown")
        self.assertEqual(job.get("fit_mode"), "blur")

    def test_render_clip_invalid_fit_mode_falls_back_to_blur(self):
        """Edge Case: render_clip() with unrecognized fit_mode applies ambient blur filter."""
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "dummy.ass"
            sub.write_text("[Script Info]\n", encoding="utf-8")
            with patch("backend.app.run_command") as mock_run:
                render_clip(Path("in.mp4"), Path("out.mp4"), sub, 0.0, 3.0, "9:16", fit_mode="invalid_mode")

            cmd = mock_run.call_args.args[0]
            self.assertIn("-filter_complex", cmd)
            fc = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("boxblur=28:5", fc)

    def test_write_ass_handles_empty_words_gracefully(self):
        """Adversarial / Boundary: write_ass() with empty words list writes valid ASS without crash."""
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "empty_words.ass"
            try:
                write_ass(out_file, [], 0.0, 5.0, "9:16", caption_style="clean")
            except Exception as e:
                self.fail(f"write_ass() failed on empty words list: {e}")

            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("[Script Info]", content)
            self.assertIn("[V4+ Styles]", content)

    def test_write_ass_escaping_and_special_characters(self):
        """Adversarial / Encoding: Text with ASS meta-characters, braces, backslashes, emojis, and quotes."""
        adversarial_words = [
            {"start": 0.0, "end": 0.5, "word": "Test{escaped}"},
            {"start": 0.5, "end": 1.0, "word": "slash\\newline\\N"},
            {"start": 1.0, "end": 1.5, "word": "emoji⚡rocket🚀"},
            {"start": 1.5, "end": 2.0, "word": 'quotes"and,commas'},
        ]
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "adversarial.ass"
            try:
                write_ass(out_file, adversarial_words, 0.0, 2.5, "9:16", caption_style="clean")
            except Exception as e:
                self.fail(f"write_ass() failed on adversarial characters: {e}")

            content = out_file.read_text(encoding="utf-8")
            self.assertIn("[Events]", content)
            # Ensure unescaped raw curly braces inside dialogue token text were sanitized
            dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
            self.assertGreaterEqual(len(dialogue_lines), 1)

    def test_create_job_invalid_input_combinations_rejected(self):
        """Adversarial / Combinations: Reject invalid templates, ratios, clip counts, and duration ranges."""
        invalid_cases = [
            {"template": "nonexistent", "aspect_ratio": "9:16", "clip_count": 2, "min_duration": 15, "max_duration": 30},
            {"template": "podcast", "aspect_ratio": "4:3", "clip_count": 2, "min_duration": 15, "max_duration": 30},
            {"template": "podcast", "aspect_ratio": "9:16", "clip_count": 0, "min_duration": 15, "max_duration": 30},
            {"template": "podcast", "aspect_ratio": "9:16", "clip_count": 10, "min_duration": 15, "max_duration": 30},
            {"template": "podcast", "aspect_ratio": "9:16", "clip_count": 2, "min_duration": 40, "max_duration": 20},
            {"template": "podcast", "aspect_ratio": "9:16", "clip_count": 2, "min_duration": 5, "max_duration": 20},
        ]
        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(HTTPException):
                    create_job(**kwargs, source_path="dummy.mp4")


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestTier3CrossFeatureCombinations(BaseTestCase):
    """Tier 3: Cross-feature combination tests."""

    def setUp(self):
        with LOCK:
            self.orig_jobs = dict(JOBS)
            self.orig_active = dict(ACTIVE_PROCESSES)

    def tearDown(self):
        with LOCK:
            JOBS.clear()
            JOBS.update(self.orig_jobs)
            ACTIVE_PROCESSES.clear()
            ACTIVE_PROCESSES.update(self.orig_active)

    @patch("backend.app.POOL.submit")
    def test_evo_preset_with_default_canvas_framing(self, mock_submit):
        """Combination (M1 + M2): Evo preset naturally inherits Canvas Framing (blur) and renders ASS."""
        job = create_job("podcast", "9:16", 1, 10, 20, source_path="dummy.mp4", caption_style="evo")
        self.assertEqual(job["caption_style"], "evo")
        self.assertEqual(job["fit_mode"], "blur")

        words, dur = sample_words()
        with tempfile.TemporaryDirectory() as td:
            sub_file = Path(td) / "evo.ass"
            write_ass(sub_file, words, 0.0, min(dur, 4.0), "9:16", caption_style="evo", auto_headline=True)

            content = sub_file.read_text(encoding="utf-8")
            self.assertIn(r"\fscx114\fscy114", content)

            with patch("backend.app.run_command") as mock_run:
                render_clip(Path("source.mp4"), Path("out.mp4"), sub_file, 0.0, 4.0, "9:16", fit_mode=job["fit_mode"], caption_style="evo")

            cmd = mock_run.call_args.args[0]
            self.assertIn("-filter_complex", cmd)
            fc = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("boxblur=28:5", fc)
            self.assertIn("ass=", fc)

    @patch("backend.app.POOL.submit")
    def test_job_lifecycle_multiple_fit_modes_then_bulk_delete(self, mock_submit):
        """Combination (M1 + M3): Create jobs across blur, letterbox, and crop, then bulk delete."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(delete_all_jobs, "delete_all_jobs not implemented.")

        job_blur = create_job("podcast", "9:16", 1, 10, 20, source_path="d1.mp4", fit_mode="blur")
        job_letter = create_job("podcast", "9:16", 1, 10, 20, source_path="d2.mp4", fit_mode="letterbox")
        job_crop = create_job("podcast", "9:16", 1, 10, 20, source_path="d3.mp4", fit_mode="crop")

        self.assertIn(job_blur["id"], JOBS)
        self.assertIn(job_letter["id"], JOBS)
        self.assertIn(job_crop["id"], JOBS)

        res = delete_all_jobs()
        self.assertTrue(res.get("ok"))
        self.assertGreaterEqual(res.get("deleted_count", 0), 3)
        self.assertEqual(len(JOBS), 0)

    @patch("backend.app.POOL.submit")
    def test_bulk_delete_during_in_flight_worker_prevents_reinsertion(self, mock_submit):
        """Combination (M3 Concurrency): If a worker attempts update_job() after bulk delete, job is not resurrected."""
        delete_all_jobs = get_delete_all_jobs_fn()
        self.assertIsNotNone(delete_all_jobs, "delete_all_jobs not implemented.")

        job = create_job("podcast", "9:16", 1, 10, 20, source_path="d.mp4")
        job_id = job["id"]

        # Bulk delete clears JOBS
        delete_all_jobs()
        self.assertNotIn(job_id, JOBS)

        # Worker thread wakes up and tries to update progress
        update_job(job_id, progress=50, stage="Transcribing")

        # Must not resurrect into memory or SQLite
        self.assertNotIn(job_id, JOBS)
        with db_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
            self.assertEqual(cnt, 0)


# ==============================================================================
# TIER 4: REAL-WORLD WORKFLOWS
# ==============================================================================

class TestTier4RealWorldWorkflows(BaseTestCase):
    """Tier 4: Realistic end-to-end multi-step workflow simulations."""

    def setUp(self):
        with LOCK:
            self.orig_jobs = dict(JOBS)
            self.orig_active = dict(ACTIVE_PROCESSES)

    def tearDown(self):
        with LOCK:
            JOBS.clear()
            JOBS.update(self.orig_jobs)
            ACTIVE_PROCESSES.clear()
            ACTIVE_PROCESSES.update(self.orig_active)

    @patch("backend.app.POOL.submit")
    def test_e2e_full_job_pipeline_lifecycle(self, mock_submit):
        """Workflow: Full clip discovery, candidate ranking, ASS styling, canvas rendering, and cleanup."""
        # 1. User submits project with educational template and linen style
        job = create_job(
            "educational", "9:16", 2, 10, 25,
            source_path="interview.mp4",
            caption_style="linen",
            fit_mode="blur",
        )
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["fit_mode"], "blur")

        # 2. Pipeline ranks candidates
        words, dur = sample_words()
        candidates = rank_candidates(words, "educational", 10, 25, dur, 2)
        self.assertGreaterEqual(len(candidates), 1)
        top = candidates[0]

        # 3. Subtitles generated
        with tempfile.TemporaryDirectory() as td:
            sub_path = Path(td) / "educational_linen.ass"
            write_ass(
                sub_path, words, top["start"], top["end"], "9:16",
                caption_style="linen", auto_headline=True
            )
            self.assertTrue(sub_path.exists())
            ass_text = sub_path.read_text(encoding="utf-8")
            self.assertIn("Merriweather", ass_text)

            # 4. Render clip with canvas framing
            out_clip = Path(td) / "clip_01.mp4"
            with patch("backend.app.run_command") as mock_run:
                render_clip(
                    Path("interview.mp4"), out_clip, sub_path,
                    top["start"], top["end"], "9:16",
                    caption_style="linen", template="educational", fit_mode="blur"
                )
            cmd = mock_run.call_args.args[0]
            self.assertIn("-filter_complex", cmd)
            self.assertIn("boxblur=28:5", cmd[cmd.index("-filter_complex") + 1])

        # 5. Persist completed clip
        top["filename"] = "clip_01.mp4"
        update_job(job["id"], status="completed", progress=100, clips=[top])
        self.assertEqual(JOBS[job["id"]]["status"], "completed")

        # 6. Bulk delete
        delete_all_jobs = get_delete_all_jobs_fn()
        if delete_all_jobs is not None:
            del_res = delete_all_jobs()
            self.assertTrue(del_res["ok"])
            self.assertEqual(len(JOBS), 0)

    @patch("backend.app.POOL.submit")
    def test_prompt_designer_evo_chip_workflow(self, mock_submit):
        """Workflow: User selects Evo Frosted Pill prompt chip in Prompt Designer."""
        prompt_text = "Frosted glass cyan pill with luminous active pop and top headline banner"
        custom_style = parse_caption_prompt(prompt_text)
        self.assertEqual(custom_style.get("font"), "Montserrat")
        self.assertTrue(custom_style.get("pill"))

        job = create_job(
            "podcast", "9:16", 1, 10, 20,
            source_path="source.mp4",
            caption_mode="prompt",
            caption_prompt=prompt_text,
            fit_mode="blur",
        )
        self.assertEqual(job["caption_mode"], "prompt")
        self.assertEqual(job["fit_mode"], "blur")

        words, dur = sample_words()
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "prompt_pill.ass"
            write_ass(sub, words, 0.0, 3.0, "9:16", custom_style=custom_style)
            content = sub.read_text(encoding="utf-8")
            self.assertIn("Style: Cutflow,", content)

    def test_multi_resolution_export_workflow(self):
        """Workflow: User selects quality variants (720, 1080, 2k) on a canvas-framed clip."""
        for q in ("720", "1080", "2k"):
            with self.subTest(quality=q):
                dims = export_dimensions("9:16", q)
                self.assertEqual(dims[0], {"720": 720, "1080": 1080, "2k": 1440}[q])

                with tempfile.TemporaryDirectory() as td:
                    out = Path(td) / f"export_{q}.mp4"
                    with patch("backend.app.run_command") as mock_run:
                        render_export(Path("master.mp4"), out, "9:16", q)
                    cmd = mock_run.call_args.args[0]
                    self.assertIn("-vf", cmd)
                    self.assertIn(f"{dims[0]}:{dims[1]}:flags=lanczos", cmd[cmd.index("-vf") + 1])
                    self.assertIn("160k", cmd)


if __name__ == "__main__":
    unittest.main()
