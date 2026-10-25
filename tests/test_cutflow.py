import os
import re
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

from backend.app import (
    CAPTION_STYLES, STYLE_PROFILES, TEMPLATES, apply_prompt_edit_plan, cancel_job,
    create_job, db_connection, download_clip, extract_headline, parse_caption_prompt,
    identify_video_style, make_title, persist_job, rank_candidates, render_clip,
    render_export, export_dimensions, write_ass,
)


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

    def test_music_template_ranking(self):
        words, duration = sample_words()
        clips = rank_candidates(words, "music", 10, 20, duration, 3, [7.5, 18.0, 29.0])
        self.assertTrue(clips)
        self.assertEqual(clips[0]["category"], "Music & performance")

    def test_music_template_prefers_chorus_over_interview_fillers(self):
        song_lyrics = "sing it out loud yeah yeah baby dance all night to the rhythm and feel the beat drop"
        song_words = [{"start": i * 0.7, "end": i * 0.7 + 0.6, "word": w} for i, w in enumerate(song_lyrics.split())]
        speech_text = "um honestly basically actually like you know erm I think that was literally crazy"
        speech_words = [{"start": i * 0.7, "end": i * 0.7 + 0.6, "word": w} for i, w in enumerate(speech_text.split())]
        song_clips = rank_candidates(song_words, "music", 8, 20, 20.0, 1, [3.0, 7.0])
        speech_clips = rank_candidates(speech_words, "music", 8, 20, 20.0, 1)
        self.assertTrue(song_clips)
        self.assertTrue(speech_clips)
        self.assertGreater(song_clips[0]["score"], speech_clips[0]["score"])


    def test_caption_presets_and_phrase_captions_stay_readable(self):
        self.assertTrue({"clean", "pulse", "glow", "hormozi", "karaoke", "prime", "impact", "paper", "elevate", "pop", "y2k", "chalk"}.issubset(set(CAPTION_STYLES)))
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
        self.assertIn(r"\fscx114\fscy114", rendered)
        dialogue_lines = [line for line in rendered.splitlines() if line.startswith("Dialogue:")]
        self.assertGreater(len(dialogue_lines), 1)
        for line in dialogue_lines:
            caption = line.split(",,", 1)[-1]
            visible_caption = re.sub(r"\{[^}]*\}", "", caption)
            self.assertLessEqual(len(visible_caption), 28)

    def test_captions_ai_prime_preset_and_kinetic_pop(self):
        words = [
            {"start": 0.0, "end": 0.4, "word": "This"},
            {"start": 0.4, "end": 0.8, "word": "crazy"},
            {"start": 0.8, "end": 1.2, "word": "growth"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / "prime.ass"
            write_ass(subtitle, words, 0, 1.5, "9:16", "prime", auto_emoji=True, kinetic_pop=True)
            content = subtitle.read_text(encoding="utf-8")
        self.assertIn(r"\c&H00FFFA93", content)
        self.assertIn(r"\fscx114\fscy114", content)
        self.assertIn("⚡", content)
        self.assertIn("🚀", content)

    def test_write_srt_and_auto_emoji_integration(self):
        from backend.app import write_srt
        words = [
            {"start": 0.0, "end": 0.5, "word": "This"},
            {"start": 0.5, "end": 1.0, "word": "secret"},
            {"start": 1.0, "end": 1.5, "word": "makes"},
            {"start": 1.5, "end": 2.0, "word": "money"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            srt_path = Path(directory) / "test.srt"
            write_srt(srt_path, words, 0, 2.5, auto_emoji=True, uppercase=True)
            content = srt_path.read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 -->", content)
        self.assertIn("💡", content)
        self.assertIn("💰", content)
        self.assertIn("MONEY", content)

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

    def test_quality_export_dimensions_cover_all_aspects_and_resolutions(self):
        expected = {("9:16", "480"): (480, 854), ("9:16", "720"): (720, 1280), ("9:16", "1080"): (1080, 1920), ("9:16", "2k"): (1440, 2560), ("1:1", "2k"): (1440, 1440), ("16:9", "480"): (854, 480), ("16:9", "720"): (1280, 720), ("16:9", "1080"): (1920, 1080), ("16:9", "2k"): (2560, 1440)}
        for (aspect, quality), dimensions in expected.items():
            with self.subTest(aspect=aspect, quality=quality):
                self.assertEqual(export_dimensions(aspect, quality), dimensions)
        with self.assertRaises(HTTPException):
            export_dimensions("9:16", "4k")

    def test_quality_export_uses_fast_cached_variant_render_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "exports" / "clip-720.mp4"
            with patch("backend.app.run_command") as run:
                render_export(Path("master.mp4"), output, "9:16", "720")
            command = run.call_args.args[0]
            self.assertIn("720:1280:flags=lanczos", command[command.index("-vf") + 1])
            self.assertIn("veryfast", command)
            self.assertIn("-c:a", command)
            self.assertIn("160k", command)
            self.assertEqual(command[-1], str(output))

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

    def test_identify_video_style_identifies_music_content(self):
        lyrics = "sing the chorus again drop the beat rhythm melody listen to this song yeah baby sing along"
        words = [{"word": w, "start": i * 0.5, "end": (i + 1) * 0.5} for i, w in enumerate(lyrics.split())]
        # Repeat the chorus phrase to trigger repetition detection
        chorus = [{"word": w, "start": 20 + i * 0.5, "end": 20 + (i + 1) * 0.5} for i, w in enumerate("sing the chorus again drop the beat rhythm melody".split())]
        all_words = words + chorus
        full_transcript = lyrics + " sing the chorus again drop the beat rhythm melody"
        result = identify_video_style(all_words, full_transcript, [1.0, 3.5, 7.0, 10.0, 15.0], 30.0, title="official_music_track.mp4")
        self.assertEqual(result["best_style"], "music")
        self.assertGreaterEqual(result["confidence"], 0.6)
        self.assertIn("music", result["scores"])

    def test_identify_video_style_identifies_gaming_content(self):
        game_dialogue = "gg clutch boss respawn match gameplay headshot level up kill weapon mod quest speedrun"
        words = [{"word": w, "start": i * 0.4, "end": (i + 1) * 0.4} for i, w in enumerate(game_dialogue.split())]
        cuts = [float(x) for x in range(1, 20)]  # fast cuts
        result = identify_video_style(words, game_dialogue, cuts, 45.0, title="fortnite_highlights.mp4")
        self.assertEqual(result["best_style"], "gaming")
        self.assertGreaterEqual(result["confidence"], 0.6)

    def test_render_clip_applies_tailored_style_filters(self):
        for style_name, profile in STYLE_PROFILES.items():
            with patch("backend.app.run_command") as run:
                render_clip(Path("source.mp4"), Path("out.mp4"), Path("captions.ass"), 2, 12, "9:16", template=style_name)
            command = run.call_args.args[0]
            filter_arg = command[command.index("-vf") + 1]
            self.assertIn(profile["eq"], filter_arg)
            self.assertIn(profile["unsharp"], filter_arg)

    def test_create_job_supports_auto_template(self):
        job = create_job("auto", "9:16", 3, 20, 45, source_path="dummy.mp4")
        self.assertEqual(job["template"], "auto")
        self.assertEqual(job["template_label"], "Smart Auto-Detect")

    @patch("backend.app.POOL.submit")
    def test_cancel_job_cancels_queued_or_processing_job(self, mock_submit):
        job = create_job("podcast", "9:16", 2, 20, 45, source_path="dummy.mp4")
        cancelled = cancel_job(job["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["stage"], "Cancelled")

    def test_cancel_nonexistent_job_raises_404(self):
        with self.assertRaises(HTTPException):
            cancel_job("0" * 32)

    def test_flagship_caption_styles_exist_and_are_emoji_free(self):
        flagship_keys = {"focus", "linen", "evo", "lift", "stack", "align"}
        self.assertTrue(flagship_keys.issubset(set(CAPTION_STYLES)))
        for key in flagship_keys:
            style = CAPTION_STYLES[key]
            self.assertTrue(style["label"])
            self.assertTrue(style["show_headline"])
            # Ensure no unicode emojis in style label
            self.assertFalse(re.search(r"[\U00010000-\U0010ffff]", style["label"]))

    def test_extract_headline_extracts_punchy_hooks(self):
        self.assertEqual(extract_headline("The biggest mistake people make in code"), "THE BIGGEST MISTAKE")
        self.assertEqual(extract_headline("Here's why you need to start today"), "HERE'S WHY YOU NEED")
        self.assertEqual(extract_headline("Drop the beat right now"), "DROP THE BEAT")
        fallback = extract_headline("Simple thoughts and ideas for success")
        self.assertTrue(fallback.isupper())
        self.assertLessEqual(len(fallback), 24)

    def test_parse_caption_prompt_parses_custom_styles(self):
        # 1. Focus badge box prompt
        focus_style = parse_caption_prompt("Inverted badge box with black text and neon cyan pop")
        self.assertTrue(focus_style.get("badge_box"))
        self.assertEqual(focus_style.get("accent_color"), "&H00FFFF00")

        # 2. Linen editorial serif prompt
        linen_style = parse_caption_prompt("Editorial serif linen layout with elegant gold pop")
        self.assertEqual(linen_style.get("font"), "DejaVu Serif")
        self.assertEqual(linen_style.get("accent_color"), "&H0000FFFF")

        # 3. Stack brutalist technical prompt
        stack_style = parse_caption_prompt("Brutalist monospace technical grid with yellow pop and vertical side text")
        self.assertEqual(stack_style.get("font"), "DejaVu Sans Mono")
        self.assertTrue(stack_style.get("vertical_side"))

    def test_multi_layer_ass_renders_headline_and_badge_boxes(self):
        words = [
            {"start": 0.0, "end": 0.4, "word": "The"},
            {"start": 0.4, "end": 0.8, "word": "biggest"},
            {"start": 0.8, "end": 1.2, "word": "mistake"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / "focus.ass"
            write_ass(subtitle, words, 0, 1.5, "9:16", "focus", auto_headline=True)
            content = subtitle.read_text(encoding="utf-8")
        self.assertIn("CutflowTitle", content)
        self.assertIn("THE BIGGEST MISTAKE", content)
        # Check inverted white badge box tag
        self.assertIn(r"\3c&H00FFFFFF\c&H00000000", content)

    @patch("backend.app.POOL.submit")
    def test_create_job_supports_dual_caption_modes(self, mock_submit):
        # Prompt mode
        job_prompt = create_job(
            "podcast", "9:16", 2, 20, 45, source_path="dummy.mp4",
            caption_mode="prompt", caption_prompt="Linen editorial serif layout with gold pop",
            auto_headline=True,
        )
        self.assertEqual(job_prompt["caption_mode"], "prompt")
        self.assertIn("Linen editorial", job_prompt["caption_prompt"])
        self.assertTrue(job_prompt["auto_headline"])

        # Auto mode with focus preset
        job_auto = create_job(
            "podcast", "9:16", 2, 20, 45, source_path="dummy.mp4",
            caption_mode="auto", caption_style="focus",
        )
        self.assertEqual(job_auto["caption_mode"], "auto")
        self.assertEqual(job_auto["caption_style"], "focus")


if __name__ == "__main__":
    unittest.main()
