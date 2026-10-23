import os
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DATA_DIR = tempfile.mkdtemp(prefix="cutflow-tests-")
os.environ["CUTFLOW_DATA_DIR"] = TEST_DATA_DIR
os.environ["CUTFLOW_DB_PATH"] = os.path.join(TEST_DATA_DIR, "cutflow-test.sqlite3")
os.environ["AI_BASE_URL"] = ""
os.environ["AI_API_KEY"] = ""
os.environ["OPENAI_BASE_URL"] = ""
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from backend.app import TEMPLATES, apply_prompt_edit_plan, create_job, db_connection, download_clip, make_title, persist_job, rank_candidates


def sample_words():
    words = []
    phrases = [
        "The biggest mistake people make is trying to learn everything at once. Start with one clear goal and practice it every single day.",
        "Here is how you can solve the problem. First understand the basics, then build a small example and test what you learned.",
        "I never expected that moment to change my life. Suddenly everything became clear and I finally understood why the story mattered.",
        "Honestly the truth is simple. You need to keep learning because every mistake teaches you something important.",
    ]
    timestamp = 0.0
    for phrase in phrases:
        for token in phrase.split():
            duration = 0.65
            words.append({"start": timestamp, "end": timestamp + duration, "word": token})
            timestamp += duration
        words[-1]["word"] += "."
        timestamp += 0.15
    return words, timestamp + 1


class CutflowTests(unittest.TestCase):
    def test_templates_have_required_fields(self):
        self.assertGreaterEqual(len(TEMPLATES), 5)
        for template in TEMPLATES.values():
            self.assertTrue(template["label"])
            self.assertTrue(template["keywords"])
            self.assertTrue(template["hooks"])

    def test_title_is_short_and_nonempty(self):
        title = make_title("This is a really long example title that should be trimmed", "podcast")
        self.assertTrue(title)
        self.assertLessEqual(len(title), 88)

    def test_candidate_durations_and_non_overlapping_selection(self):
        words, duration = sample_words()
        clips = rank_candidates(words, "educational", 10, 20, duration, 3, [7.5, 18.0, 29.0])
        self.assertTrue(clips)
        self.assertLessEqual(len(clips), 3)
        for clip in clips:
            self.assertGreaterEqual(clip["duration"], 10)
            self.assertLessEqual(clip["duration"], 20)
        for previous, current in zip(clips, clips[1:]):
            self.assertGreaterEqual(current["start"], previous["start"])

    def test_prompt_falls_back_cleanly_when_ai_not_configured(self):
        candidates = [{"start": 1, "end": 12, "score": 60, "title": "A clip", "text": "sample"}]
        selected, warning = apply_prompt_edit_plan(candidates, "sample transcript", "Keep the complete explanation", "educational")
        self.assertEqual(selected, candidates)
        self.assertIsNotNone(warning)
        self.assertIn("not configured", warning)

    def test_job_metadata_is_persisted_to_sqlite(self):
        job = {"id": "a" * 32, "created_at": 1.0, "updated_at": 1.0, "status": "queued"}
        persist_job(job)
        with db_connection() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE id = ?", (job["id"],)).fetchone()
        self.assertIsNotNone(row)
        self.assertIn(job["id"], row["payload"])

    def test_invalid_clip_count_is_rejected(self):
        with self.assertRaises(HTTPException):
            create_job("podcast", "9:16", 99, 20, 45)

    def test_clip_download_rejects_invalid_project_id(self):
        with self.assertRaises(HTTPException):
            download_clip("../outside", "cutflow-01.mp4")

    def test_prompt_without_brief_does_not_call_provider(self):
        candidates = [{"start": 1, "end": 12, "score": 60}]
        selected, warning = apply_prompt_edit_plan(candidates, "sample", "", "podcast")
        self.assertEqual(selected, candidates)
        self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
