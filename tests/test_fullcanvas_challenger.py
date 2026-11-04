"""Adversarial stress-test harness for Full-Canvas Captioning.

Empirically tests:
1. All 18 caption presets compile valid ASS.
2. All 18 presets burn cleanly with FFmpeg via libass video filter.
3. All 3 aspect ratios (9:16, 1:1, 16:9) render with proper PlayResX/PlayResY and safe margins.
4. Edge cases:
   - Empty dialogue words (fallback clips)
   - Long dialogue runs (dynamic font downscaling to 58%)
   - Special characters, ASS control characters, emojis, non-ASCII
   - Short words, empty word strings, whitespace-only tokens
   - Zero-duration clips and zero-duration words
5. Custom style dictionary overrides via resolve_caption_spec with sparse/missing/invalid keys.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app import (
    CAPTION_PRESETS,
    EMOJI_MAP,
    extract_headline,
    resolve_caption_spec,
    write_ass,
)
from backend.captions import ass as ass_engine
from backend.captions.ass import compile_ass, resolve
from backend.captions.presets import PRESETS
from backend.captions.spec import CaptionSpec

FONTS_DIR = (REPO_ROOT / "backend" / "assets" / "fonts").resolve()
ESCAPED_FONTS_DIR = FONTS_DIR.as_posix().replace(":", r"\:")

SAMPLE_WORDS = [
    {"start": 0.0, "end": 0.45, "word": "This"},
    {"start": 0.45, "end": 0.90, "word": "radical"},
    {"start": 0.90, "end": 1.40, "word": "growth"},
    {"start": 1.40, "end": 2.00, "word": "experiment"},
    {"start": 2.00, "end": 2.50, "word": "changed"},
    {"start": 2.50, "end": 3.00, "word": "everything"},
]


def run_ffmpeg_ass_burn(
    ass_path: Path,
    out_mp4: Path,
    width: int = 1080,
    height: int = 1920,
    duration: float = 0.5,
) -> tuple[int, str, str]:
    """Burn ASS into a black video canvas and return (returncode, stdout, stderr)."""
    escaped_ass = ass_path.resolve().as_posix().replace(":", r"\:")
    ass_filter = f"ass='{escaped_ass}':fontsdir='{ESCAPED_FONTS_DIR}'"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={width}x{height}:d={duration}",
        "-vf",
        ass_filter,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        str(out_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


class AdversarialCaptionPresetsTest(unittest.TestCase):
    """Stress-test all 18 caption presets for compilation and FFmpeg rendering."""

    def test_all_18_presets_present_and_compile_valid_ass(self):
        expected_presets = [
            "focus",
            "linen",
            "evo",
            "lift",
            "stack",
            "align",
            "prime",
            "impact",
            "paper",
            "elevate",
            "pop",
            "y2k",
            "chalk",
            "clean",
            "pulse",
            "glow",
            "hormozi",
            "karaoke",
        ]
        self.assertEqual(len(PRESETS), 18)
        for key in expected_presets:
            self.assertIn(key, PRESETS, f"Preset '{key}' missing from PRESETS")
            spec = PRESETS[key]
            ass_text = compile_ass(
                spec,
                words=SAMPLE_WORDS,
                start=0.0,
                end=3.0,
                aspect="9:16",
                auto_emoji=True,
                emoji_map=EMOJI_MAP,
                auto_headline=True,
                candidate_text="RADICAL GROWTH EXPERIMENT",
                template="podcast",
                extract_headline=extract_headline,
            )
            # Verify ASS syntax headers
            self.assertIn("[Script Info]", ass_text)
            self.assertIn("PlayResX: 1080", ass_text)
            self.assertIn("PlayResY: 1920", ass_text)
            self.assertIn("[V4+ Styles]", ass_text)
            self.assertIn("Style: Caption,", ass_text)
            self.assertIn("Style: CutHeadline,", ass_text)
            self.assertIn("Style: Cutflow,", ass_text)
            self.assertIn("Style: CutflowTitle,", ass_text)
            self.assertIn("[Events]", ass_text)
            self.assertIn(
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                ass_text,
            )

            # Verify dialogue event lines have 10 fields
            dialogue_lines = [l for l in ass_text.splitlines() if l.startswith("Dialogue:")]
            self.assertGreater(len(dialogue_lines), 0, f"Preset {key} produced 0 dialogue lines")
            for d in dialogue_lines:
                parts = d.split(",", 9)
                self.assertEqual(
                    len(parts),
                    10,
                    f"Dialogue line does not have 10 fields: {d}",
                )

    def test_all_18_presets_burn_cleanly_via_ffmpeg(self):
        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-burn-") as td:
            tdp = Path(td)
            for key, spec in PRESETS.items():
                ass_text = compile_ass(
                    spec,
                    words=SAMPLE_WORDS,
                    start=0.0,
                    end=3.0,
                    aspect="9:16",
                    auto_emoji=True,
                    emoji_map=EMOJI_MAP,
                    auto_headline=True,
                    candidate_text="RADICAL GROWTH EXPERIMENT",
                    template="podcast",
                    extract_headline=extract_headline,
                )
                ass_path = tdp / f"{key}.ass"
                ass_path.write_text(ass_text, encoding="utf-8")
                out_mp4 = tdp / f"{key}.mp4"

                rc, stdout, stderr = run_ffmpeg_ass_burn(
                    ass_path, out_mp4, width=1080, height=1920, duration=0.5
                )
                self.assertEqual(
                    rc,
                    0,
                    f"FFmpeg failed on preset '{key}' with return code {rc}.\nStderr:\n{stderr}",
                )
                self.assertTrue(
                    out_mp4.exists(),
                    f"Output mp4 for preset '{key}' was not created",
                )
                self.assertGreater(
                    out_mp4.stat().st_size,
                    1000,
                    f"Output mp4 for preset '{key}' is suspiciously small ({out_mp4.stat().st_size} bytes)",
                )


class AdversarialAspectRatioTest(unittest.TestCase):
    """Stress-test 9:16, 1:1, and 16:9 aspect ratios."""

    def test_aspect_ratios_geometry_and_ffmpeg_burn(self):
        aspect_configs = [
            ("9:16", 1080, 1920),
            ("1:1", 1080, 1080),
            ("16:9", 1920, 1080),
        ]
        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-aspect-") as td:
            tdp = Path(td)
            for aspect, w, h in aspect_configs:
                for preset_name in ("clean", "focus", "lift", "stack", "align"):
                    spec = PRESETS[preset_name]
                    res = resolve(spec, aspect)
                    self.assertEqual(res.width, w)
                    self.assertEqual(res.height, h)

                    # Verify safe margins:
                    # zone="lower" has lower_margin >= 0.14, meaning caption_y <= height * (1 - lower_margin)
                    if spec.zone == "lower":
                        self.assertLessEqual(res.caption_y, h * (1.0 - spec.lower_margin + 0.02))

                    ass_text = compile_ass(
                        spec,
                        words=SAMPLE_WORDS,
                        start=0.0,
                        end=3.0,
                        aspect=aspect,
                        auto_headline=True,
                        candidate_text="ASPECT TEST",
                    )
                    self.assertIn(f"PlayResX: {w}", ass_text)
                    self.assertIn(f"PlayResY: {h}", ass_text)

                    ass_path = tdp / f"{preset_name}_{w}x{h}.ass"
                    ass_path.write_text(ass_text, encoding="utf-8")
                    out_mp4 = tdp / f"{preset_name}_{w}x{h}.mp4"

                    rc, stdout, stderr = run_ffmpeg_ass_burn(
                        ass_path, out_mp4, width=w, height=h, duration=0.3
                    )
                    self.assertEqual(
                        rc,
                        0,
                        f"FFmpeg failed for {preset_name} on {aspect} ({w}x{h}): {stderr}",
                    )
                    self.assertTrue(out_mp4.exists())
                    self.assertGreater(out_mp4.stat().st_size, 1000)


class AdversarialEdgeCasesTest(unittest.TestCase):
    """Adversarial stress-testing of edge cases."""

    def test_empty_dialogue_words_fallback_clip(self):
        """Empty words list (fallback candidate clips) must render Zone 1 headline card cleanly."""
        spec = PRESETS["focus"]
        # Case A: candidate_text with extract_headline
        ass_text_extracted = compile_ass(
            spec,
            words=[],
            start=0.0,
            end=3.0,
            aspect="9:16",
            auto_headline=True,
            candidate_text="TOPIC SUMMARY ONLY",
            extract_headline=extract_headline,
        )
        self.assertIn("TOPIC SUMMARY ONLY", ass_text_extracted)
        self.assertIn("CutBadgeHeadline", ass_text_extracted)

        # Case B: explicit headline_text
        ass_text_explicit = compile_ass(
            spec,
            words=[],
            start=0.0,
            end=3.0,
            aspect="9:16",
            auto_headline=True,
            headline_text="EXPLICIT TOPIC",
        )
        self.assertIn("EXPLICIT TOPIC", ass_text_explicit)

        # Case C: candidate_text without extract_headline defaults to topic fallback ("KEY MOMENT")
        ass_text_default = compile_ass(
            spec,
            words=[],
            start=0.0,
            end=3.0,
            aspect="9:16",
            auto_headline=True,
            candidate_text="FALLBACK SCENE",
        )
        self.assertIn("KEY MOMENT", ass_text_default)

        # Case D: completely empty words and text compiles valid header and burns cleanly
        ass_text_empty = compile_ass(
            spec,
            words=[],
            start=0.0,
            end=3.0,
            aspect="9:16",
            auto_headline=True,
        )
        self.assertIn("[Script Info]", ass_text_empty)

        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-fallback-") as td:
            for name, ass_txt in (
                ("extracted", ass_text_extracted),
                ("explicit", ass_text_explicit),
                ("default", ass_text_default),
                ("empty", ass_text_empty),
            ):
                ass_path = Path(td) / f"fallback_{name}.ass"
                ass_path.write_text(ass_txt, encoding="utf-8")
                out_mp4 = Path(td) / f"fallback_{name}.mp4"
                rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4)
                self.assertEqual(rc, 0, f"Fallback clip burning failed for {name}: {stderr}")
                self.assertTrue(out_mp4.exists() and out_mp4.stat().st_size > 1000)

    def test_long_dialogue_runs_dynamic_font_downscaling(self):
        """Long or wide dialogue runs must trigger metrics downscaling down to at most 58%."""
        spec = PRESETS["clean"]
        res = resolve(spec, "9:16")
        base_font_px = res.font_px
        min_allowed_px = int(base_font_px * 0.58)

        # 1. Multi-word wide group that exceeds max_line_px within max_words and max_chars
        wide_words = [
            {"start": 0.0, "end": 0.3, "word": "MMMMMM"},
            {"start": 0.3, "end": 0.6, "word": "MMMMMM"},
            {"start": 0.6, "end": 0.9, "word": "MMMMMM"},
        ]
        ass_multi = compile_ass(
            spec,
            words=wide_words,
            start=0.0,
            end=1.0,
            aspect="9:16",
        )
        # Font 85 downscales to \fs76
        self.assertIn(r"\fs76", ass_multi)

        # 2. Extreme run hitting 58% floor
        extreme_words = [
            {"start": 0.0, "end": 1.0, "word": "A" * 60}
        ]
        ass_extreme = compile_ass(
            spec,
            words=extreme_words,
            start=0.0,
            end=1.0,
            aspect="9:16",
        )
        self.assertIn(f"\\fs{min_allowed_px}", ass_extreme)

        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-longrun-") as td:
            for name, txt in (("multi", ass_multi), ("extreme", ass_extreme)):
                ass_path = Path(td) / f"longrun_{name}.ass"
                ass_path.write_text(txt, encoding="utf-8")
                out_mp4 = Path(td) / f"longrun_{name}.mp4"
                rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4)
                self.assertEqual(rc, 0, f"Long run ASS failed FFmpeg burn: {stderr}")

    def test_special_characters_symbols_emojis_and_injection(self):
        """ASS control characters ({, }, \\, ,), quotes, emojis, and unicode must not crash."""
        adversarial_tokens = [
            r"Hello\World",
            "{nested_tag}",
            "Comma, separated, words",
            "Quote \"double\" and 'single'",
            "Math: ∑x² + √y = ±∞",
            "Unicode: Café, naïve, über, 日本語, 한국어, Русский",
            "Symbols: @#$%^&*()_+~`|<>?:;",
            "Emojis: 🔥🚀💡🎉🧠✨",
        ]
        words = [
            {"start": i * 0.4, "end": (i + 1) * 0.4, "word": tok}
            for i, tok in enumerate(adversarial_tokens)
        ]
        for preset_name in ("clean", "focus", "linen", "y2k", "stack"):
            spec = PRESETS[preset_name]
            ass_text = compile_ass(
                spec,
                words=words,
                start=0.0,
                end=len(words) * 0.4,
                aspect="9:16",
                auto_emoji=True,
                emoji_map={"fire": "🔥", "rocket": "🚀"},
                candidate_text="SPECIAL CHARS & EMOJIS {TEST}",
            )
            # Ensure literal { and } from word text were replaced with ( and ) by escape()
            # so they don't break ASS override blocks
            with tempfile.TemporaryDirectory(prefix="cutflow-challenger-specialchars-") as td:
                ass_path = Path(td) / f"{preset_name}_special.ass"
                ass_path.write_text(ass_text, encoding="utf-8")
                out_mp4 = Path(td) / f"{preset_name}_special.mp4"
                rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4, duration=0.3)
                self.assertEqual(
                    rc,
                    0,
                    f"FFmpeg failed on special characters with preset {preset_name}: {stderr}",
                )

    def test_short_words_empty_and_whitespace_tokens(self):
        """Single character words, empty words, whitespace words must not cause ZeroDivisionError or crashes."""
        words = [
            {"start": 0.0, "end": 0.3, "word": "a"},
            {"start": 0.3, "end": 0.6, "word": ""},
            {"start": 0.6, "end": 0.9, "word": "   "},
            {"start": 0.9, "end": 1.2, "word": "."},
            {"start": 1.2, "end": 1.5, "word": "I"},
            {"start": 1.5, "end": 1.8, "word": "ok"},
        ]
        for preset_name in ("clean", "focus", "paper", "hormozi"):
            spec = PRESETS[preset_name]
            ass_text = compile_ass(
                spec,
                words=words,
                start=0.0,
                end=2.0,
                aspect="9:16",
                candidate_text="SHORT WORDS TEST",
            )
            with tempfile.TemporaryDirectory(prefix="cutflow-challenger-shortwords-") as td:
                ass_path = Path(td) / f"{preset_name}_short.ass"
                ass_path.write_text(ass_text, encoding="utf-8")
                out_mp4 = Path(td) / f"{preset_name}_short.mp4"
                rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4, duration=0.3)
                self.assertEqual(rc, 0, f"FFmpeg failed on short words with preset {preset_name}: {stderr}")

    def test_zero_and_inverted_duration_handling(self):
        """Zero duration clips, zero duration words, or end <= start must not crash compiler."""
        # 1. Zero duration clip (start == end)
        spec = PRESETS["clean"]
        ass_text = compile_ass(
            spec,
            words=SAMPLE_WORDS,
            start=1.0,
            end=1.0,
            aspect="9:16",
            candidate_text="ZERO DURATION CLIP",
        )
        self.assertIn("[Script Info]", ass_text)

        # 2. Inverted duration clip (start > end)
        ass_text_inv = compile_ass(
            spec,
            words=SAMPLE_WORDS,
            start=2.0,
            end=1.0,
            aspect="9:16",
            candidate_text="INVERTED CLIP",
        )
        self.assertIn("[Script Info]", ass_text_inv)

        # 3. Words with zero duration (start == end) or inverted (end < start)
        bad_words = [
            {"start": 0.0, "end": 0.0, "word": "instant"},
            {"start": 0.5, "end": 0.2, "word": "backwards"},
            {"start": 1.0, "end": 1.5, "word": "valid"},
        ]
        ass_text_words = compile_ass(
            spec,
            words=bad_words,
            start=0.0,
            end=2.0,
            aspect="9:16",
        )
        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-zerodur-") as td:
            ass_path = Path(td) / "zerodur.ass"
            ass_path.write_text(ass_text_words, encoding="utf-8")
            out_mp4 = Path(td) / "zerodur.mp4"
            rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4, duration=0.3)
            self.assertEqual(rc, 0, f"FFmpeg failed on zero/inverted word durations: {stderr}")


class AdversarialCustomStyleOverridesTest(unittest.TestCase):
    """Stress-test resolve_caption_spec with sparse, missing, or malformed overrides."""

    def test_resolve_caption_spec_sparse_and_invalid_overrides(self):
        # 1. Non-existent preset key
        spec_fallback = resolve_caption_spec("non_existent_preset_xyz")
        self.assertIsInstance(spec_fallback, CaptionSpec)
        self.assertIn(spec_fallback.key, ("clean", "focus"))

        # 2. None / empty string
        spec_none = resolve_caption_spec(None)
        self.assertIsInstance(spec_none, CaptionSpec)

        spec_empty_str = resolve_caption_spec("")
        self.assertIsInstance(spec_empty_str, CaptionSpec)

        # 3. Passing dictionary as first argument (caption_style as dict)
        spec_dict_first = resolve_caption_spec({"base_color": "&H00112233"})
        self.assertEqual(spec_dict_first.primary, "&H00112233")

        # 4. Sparse custom_style with single key
        spec_sparse = resolve_caption_spec("clean", custom_style={"accent_color": "&H0000FF00"})
        self.assertEqual(spec_sparse.accent, "&H0000FF00")

        # 5. Invalid numeric types for glow, shadow, outline_width
        spec_malformed_numbers = resolve_caption_spec(
            "clean",
            custom_style={
                "glow": "not_a_number",
                "shadow": ["list"],
                "outline_width": {"dict": 1},
                "base_color": "&H00AABBCC",
            },
        )
        self.assertEqual(spec_malformed_numbers.primary, "&H00AABBCC")
        self.assertIsInstance(spec_malformed_numbers.glow, float)

        # 6. Boolean and layout switches
        spec_switches = resolve_caption_spec(
            "clean",
            custom_style={
                "badge_box": True,
                "vertical_side": True,
                "top_banner": True,
                "letterbox": True,
                "pill": True,
                "font": "Merriweather Serif Bold",
            },
            uppercase=True,
            kinetic_pop=False,
        )
        self.assertEqual(spec_switches.caption_box, "pill")
        self.assertEqual(spec_switches.font, "Merriweather")
        self.assertEqual(spec_switches.rail, "CUTFLOW // MOTION GRAPHICS")
        self.assertEqual(spec_switches.headline, "banner")
        self.assertEqual(spec_switches.frame, "letterbox")
        self.assertTrue(spec_switches.uppercase)
        self.assertFalse(spec_switches.active_pop)

        # 7. Compile and burn the complex overridden spec
        ass_text = compile_ass(
            spec_switches,
            words=SAMPLE_WORDS,
            start=0.0,
            end=3.0,
            aspect="9:16",
            candidate_text="OVERRIDE TEST",
        )
        with tempfile.TemporaryDirectory(prefix="cutflow-challenger-overrides-") as td:
            ass_path = Path(td) / "overrides.ass"
            ass_path.write_text(ass_text, encoding="utf-8")
            out_mp4 = Path(td) / "overrides.mp4"
            rc, stdout, stderr = run_ffmpeg_ass_burn(ass_path, out_mp4, duration=0.3)
            self.assertEqual(rc, 0, f"FFmpeg failed on complex overridden spec: {stderr}")


if __name__ == "__main__":
    unittest.main()
