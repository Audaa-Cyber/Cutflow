import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TEST_DATA_DIR = tempfile.mkdtemp(prefix="cutflow-tests-")
os.environ["CUTFLOW_DATA_DIR"] = TEST_DATA_DIR
os.environ["CUTFLOW_DB_PATH"] = os.path.join(TEST_DATA_DIR, "cutflow-test.sqlite3")
os.environ["AI_BASE_URL"] = ""
os.environ["AI_API_KEY"] = ""
os.environ["OPENAI_BASE_URL"] = ""
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from backend.app import CAPTION_STYLES, TEMPLATES, apply_prompt_edit_plan, create_job, db_connection, download_clip, make_title, persist_job, rank_candidates, render_clip, write_ass


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


    def test_caption_presets_and_phrase_captions_stay_readable(self):
        self.assertEqual(set(CAPTION_STYLES), {"clean", "pulse", "glow"})
        words = [
            {"start": i * 0.4, "end": i * 0.4 + 0.3, "word": word}
            for i, word in enumerate("This is a really useful explanation that should remain inside the frame.".split())
        ]
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / "captions.ass"
            write_ass(subtitle, words, 0, 8, "9:16", "pulse")
            rendered = subtitle.read_text(encoding="utf-8")
        self.assertIn("PlayResY: 1920", rendered)
        self.assertIn("DejaVu Sans", rendered)
        self.assertIn("MarginV", rendered)
        self.assertIn(r"\c&H0066F4C6", rendered)
        dialogue_lines = [line for line in rendered.splitlines() if line.startswith("Dialogue:")]
        self.assertGreater(len(dialogue_lines), 1)
        for line in dialogue_lines:
            caption = line.split(",,", 1)[-1]
            self.assertLessEqual(len(caption), 70)

    def test_caption_layout_supports_all_output_ratios(self):
        words = [{"start": 0.2, "end": 0.8, "word": "Hello world."}]
        expected = {"9:16": "PlayResY: 1920", "1:1": "PlayResY: 1080", "16:9": "PlayResX: 1920"}
        with tempfile.TemporaryDirectory() as directory:
            for aspect, marker in expected.items():
                subtitle = Path(directory) / f"{aspect.replace(':', '-')}.ass"
                write_ass(subtitle, words, 0, 2, aspect, "clean")
                self.assertIn(marker, subtitle.read_text(encoding="utf-8"))

    def test_render_pipeline_uses_subtle_finishing_and_preserves_audio(self):
        with patch("backend.app.run_command") as run:
            render_clip(Path("source.mp4"), Path("out.mp4"), Path("captions.ass"), 2, 12, "9:16")
        command = run.call_args.args[0]
        filter_arg = command[command.index("-vf") + 1]
        self.assertIn("eq=contrast=1.04:saturation=1.06", filter_arg)
        self.assertIn("unsharp=5:5:0.25", filter_arg)
        self.assertIn("ass=", filter_arg)
        self.assertIn("-c:a", command)
        self.assertIn("160k", command)

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
