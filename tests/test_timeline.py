"""Unit & API Integration Tests for Phase 1 Kinetic Timeline & Acoustic Alignment.

Validates:
1. Phonological Syllabification (nucleus detection, silent 'e', consonant clusters).
2. Syllable & Stress Peak Timings (monotonicity, interval coverage, vowel energy peaks).
3. Lexical & Acoustic Stress Scoring (viral keywords vs function words, elongation, punctuation).
4. KineticTimeline Schema Conformance (sub-millisecond resolution, visual bounds, styling metadata).
5. FastApi /api/jobs/{id}/candidates and /api/jobs/{id}/clips/{filename}/timeline endpoints.
"""

from __future__ import annotations

import unittest
from starlette.testclient import TestClient

from backend.app import app, JOBS, LOCK, create_job
from backend.captions.presets import PRESETS
from backend.captions.timeline import (
    ass_color_to_hex,
    build_kinetic_timeline,
    build_word_token,
    calculate_stress_score,
    calculate_syllable_timings,
    estimate_syllables,
)


class TestKineticTimelinePhase1(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    # ── 1. Phonological Syllabification ───────────────────────────────────────

    def test_syllable_estimation_monosyllabic_and_silent_e(self):
        # Monosyllabic words
        self.assertEqual(estimate_syllables("the"), ["the"])
        self.assertEqual(estimate_syllables("code"), ["code"])  # silent 'e'
        self.assertEqual(estimate_syllables("make"), ["make"])  # silent 'e'
        self.assertEqual(estimate_syllables("growth"), ["growth"])

    def test_syllable_estimation_polysyllabic_words(self):
        # Polysyllabic words split across nuclei
        big_syl = estimate_syllables("biggest")
        self.assertGreaterEqual(len(big_syl), 2)
        self.assertEqual("".join(big_syl), "biggest")

        mis_syl = estimate_syllables("mistake")
        self.assertGreaterEqual(len(mis_syl), 2)
        self.assertEqual("".join(mis_syl), "mistake")

        cap_syl = estimate_syllables("captions")
        self.assertGreaterEqual(len(cap_syl), 2)
        self.assertEqual("".join(cap_syl), "captions")

    # ── 2. Syllable & Stress Peak Timings ─────────────────────────────────────

    def test_syllable_timings_monotonicity_and_bounds(self):
        start_ms = 1200
        end_ms = 1850
        syllables = ["mis", "take"]
        peak_ms, s_data = calculate_syllable_timings("mistake", start_ms, end_ms, syllables)

        # Monotonicity & complete interval coverage
        self.assertEqual(s_data[0]["start_ms"], start_ms)
        self.assertEqual(s_data[-1]["end_ms"], end_ms)
        self.assertEqual(s_data[0]["end_ms"], s_data[1]["start_ms"])

        # Peak must lie strictly within the word time interval
        self.assertGreaterEqual(peak_ms, start_ms)
        self.assertLessEqual(peak_ms, end_ms)

        # Stressed syllable detection (iambic for 'mistake' -> syllable 1)
        self.assertTrue(s_data[1]["is_stressed"])
        self.assertEqual(peak_ms, s_data[1]["stress_peak_ms"])

    # ── 3. Lexical & Acoustic Stress Scoring ──────────────────────────────────

    def test_stress_scoring_viral_vs_function_words(self):
        # Viral keyword vs grammatical function word
        viral_score = calculate_stress_score("biggest", 450, 7, "biggest")
        func_score = calculate_stress_score("the", 150, 3, "the")
        self.assertGreater(viral_score, 0.70)
        self.assertLess(func_score, 0.45)

        # Acoustic elongation & emphatic punctuation boosts
        elongated = calculate_stress_score("huge", 800, 4, "HUGE!")
        standard = calculate_stress_score("huge", 200, 4, "huge")
        self.assertGreater(elongated, standard)
        self.assertGreaterEqual(elongated, 0.90)

    # ── 4. KineticTimeline Schema Conformance ─────────────────────────────────

    def test_build_word_token_and_bounds_estimation(self):
        raw = {"start": 1.25, "end": 1.75, "word": "VIRAL!"}
        token = build_word_token(raw, idx=0, font_size_px=86)
        
        self.assertEqual(token.start_ms, 1250)
        self.assertEqual(token.end_ms, 1750)
        self.assertEqual(token.duration_ms, 500)
        self.assertTrue(token.highlight)
        self.assertIsNotNone(token.bounds_estimated)
        self.assertGreater(token.bounds_estimated["approx_width_px"], 0)

    def test_build_kinetic_timeline_full_hierarchy(self):
        words = [
            {"start": 10.0, "end": 10.4, "word": "The"},
            {"start": 10.4, "end": 10.9, "word": "biggest"},
            {"start": 10.9, "end": 11.5, "word": "secret"},
            {"start": 11.5, "end": 12.0, "word": "revealed!"},
        ]
        spec = PRESETS["focus"]
        timeline = build_kinetic_timeline(
            words,
            clip_start=10.0,
            clip_end=12.5,
            spec=spec,
            aspect="9:16",
            headline_text="KEY HOOK",
            clip_id="test_clip_01",
        )

        self.assertEqual(timeline["version"], "1.0")
        self.assertEqual(timeline["clip_id"], "test_clip_01")
        self.assertEqual(timeline["start_ms"], 10000)
        self.assertEqual(timeline["end_ms"], 12500)
        self.assertEqual(timeline["word_count"], 4)
        self.assertEqual(len(timeline["words"]), 4)
        self.assertGreaterEqual(len(timeline["phrases"]), 1)

        # Validate styling metadata
        meta = timeline["styling_metadata"]
        self.assertEqual(meta["preset_key"], "focus")
        self.assertEqual(meta["font"], "Montserrat")
        self.assertIn("spring_physics", meta)
        self.assertEqual(meta["spring_physics"]["tension"], 280)
        self.assertEqual(meta["colors"]["primary"], "#ffffff")
        self.assertEqual(meta["colors"]["accent"], "#ffff00")

    def test_ass_color_conversion(self):
        # ASS &H0000FFFF (Yellow) -> #ffff00
        self.assertEqual(ass_color_to_hex("&H0000FFFF"), "#ffff00")
        # ASS &H00FFFFFF (White) -> #ffffff
        self.assertEqual(ass_color_to_hex("&H00FFFFFF"), "#ffffff")
        # ASS &H00D5FF5F (Lime) -> #5fffd5
        self.assertEqual(ass_color_to_hex("&H00D5FF5F"), "#5fffd5")

    # ── 5. REST API Candidates & Timeline Endpoints ───────────────────────────

    def test_api_jobs_candidates_and_timeline_endpoints(self):
        # Create a mock job directly in JOBS
        job_id = "a1b2c3d4e5f6789012345678abcdef01"
        spec = PRESETS["focus"]
        raw_words = [
            {"start": 0.0, "end": 0.5, "word": "Create"},
            {"start": 0.5, "end": 1.0, "word": "viral"},
            {"start": 1.0, "end": 1.5, "word": "clips"},
        ]
        timeline = build_kinetic_timeline(
            raw_words, 0.0, 2.0, spec, aspect="9:16", headline_text="VIRAL CLIPS"
        )
        
        candidate_data = {
            "start": 0.0,
            "end": 2.0,
            "duration": 2.0,
            "text": "Create viral clips",
            "score": 92,
            "category": "Podcast & conversation",
            "title": "VIRAL CLIPS",
            "clip_index": 1,
            "words": timeline["words"],
            "timeline": timeline,
            "filename": "cutflow-01.mp4",
        }

        with LOCK:
            JOBS[job_id] = {
                "id": job_id,
                "status": "completed",
                "created_at": 1000.0,
                "updated_at": 1001.0,
                "candidates": [candidate_data],
                "clips": [candidate_data],
            }

        try:
            # 1. Test /api/jobs/{job_id}/candidates
            res_cand = self.client.get(f"/api/jobs/{job_id}/candidates")
            self.assertEqual(res_cand.status_code, 200)
            data_cand = res_cand.json()
            self.assertEqual(data_cand["job_id"], job_id)
            self.assertEqual(data_cand["count"], 1)
            self.assertIn("timeline", data_cand["candidates"][0])
            self.assertEqual(data_cand["candidates"][0]["timeline"]["word_count"], 3)
            self.assertEqual(data_cand["candidates"][0]["timeline"]["words"][1]["word"], "viral")
            self.assertEqual(data_cand["candidates"][0]["timeline"]["words"][1]["syllables"][0]["text"], "vi")

            # 2. Test /api/jobs/{job_id}/clips/{filename}/timeline
            res_time = self.client.get(f"/api/jobs/{job_id}/clips/cutflow-01.mp4/timeline")
            self.assertEqual(res_time.status_code, 200)
            data_time = res_time.json()
            self.assertEqual(data_time["version"], "1.0")
            self.assertEqual(data_time["styling_metadata"]["preset_key"], "focus")
            self.assertEqual(data_time["words"][0]["word"], "Create")

            # 3. Test 404 for invalid job id
            res_404 = self.client.get("/api/jobs/nonexistentjobid12345678901234/candidates")
            self.assertEqual(res_404.status_code, 404)
        finally:
            with LOCK:
                JOBS.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()

