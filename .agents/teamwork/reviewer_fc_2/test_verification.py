import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import tempfile
import subprocess
import os
import re
from backend.captions.presets import PRESETS
from backend.captions.ass import compile_ass, resolve
from backend.app import resolve_caption_spec, write_ass, EMOJI_MAP, extract_headline, CAPTION_STYLES

fonts_dir = Path("backend/assets/fonts").resolve().as_posix().replace(":", r"\:")

words = [
    {"start": 0.0, "end": 0.5, "word": "This"},
    {"start": 0.5, "end": 1.0, "word": "is"},
    {"start": 1.0, "end": 1.5, "word": "an"},
    {"start": 1.5, "end": 2.0, "word": "extreme"},
    {"start": 2.0, "end": 2.5, "word": "growth"},
    {"start": 2.5, "end": 3.0, "word": "test"},
]

print("=== 1. PRESETS & STYLES INTEGRITY ===")
assert len(PRESETS) == 18, f"Expected 18 presets, got {len(PRESETS)}"
assert len(CAPTION_STYLES) == 18, f"Expected 18 styles, got {len(CAPTION_STYLES)}"
assert set(PRESETS.keys()) == set(CAPTION_STYLES.keys())
print("18 presets and styles perfectly match!")

print("\n=== 2. 18 PRESET FFMPEG BURNING VERIFICATION ===")
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    for key, spec in PRESETS.items():
        ass_content = compile_ass(
            spec,
            words=words,
            start=0.0,
            end=3.0,
            aspect="9:16",
            auto_emoji=True,
            emoji_map=EMOJI_MAP,
            auto_headline=True,
            candidate_text="ADVERSARIAL STRESS TEST HEADLINE",
            template="podcast",
            extract_headline=extract_headline,
        )
        ass_path = tdp / f"{key}.ass"
        ass_path.write_text(ass_content, encoding="utf-8")
        escaped_ass = ass_path.resolve().as_posix().replace(":", r"\:")
        out_mp4 = tdp / f"{key}.mp4"
        ass_filter = f"ass='{escaped_ass}':fontsdir='{fonts_dir}'"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=0.25",
            "-vf", ass_filter,
            "-c:v", "libx264", "-preset", "ultrafast", str(out_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FAILED on preset {key}: {res.stderr}")
            exit(1)
        assert out_mp4.exists() and out_mp4.stat().st_size > 0
        print(f"Preset {key:10s}: OK ({out_mp4.stat().st_size} bytes)")

print("\n=== 3. ADVERSARIAL EDGE CASES FFMPEG BURNING ===")
adversarial_cases = [
    # Case 1: Empty words list (fallback candidate)
    {
        "name": "fallback_empty_words",
        "spec": PRESETS["focus"],
        "words": [],
        "candidate_text": "FALLBACK VISUAL CLIP TOPIC",
        "aspect": "9:16",
        "duration": 2.0,
    },
    # Case 2: Special ASS characters, curly braces, quotes, slashes, emojis
    {
        "name": "special_chars_escaping",
        "spec": PRESETS["stack"],
        "words": [
            {"start": 0.0, "end": 0.5, "word": "Hello{test}"},
            {"start": 0.5, "end": 1.0, "word": "slash\\newline\\N"},
            {"start": 1.0, "end": 1.5, "word": "comma,quote\""},
            {"start": 1.5, "end": 2.0, "word": "emoji⚡rocket🚀"},
        ],
        "candidate_text": "HOOK WITH {BRACES} AND \\BACKSLASH",
        "aspect": "9:16",
        "duration": 2.0,
    },
    # Case 3: Ultra long word (100 characters) to test safe margins downscaling
    {
        "name": "long_word_downscaling",
        "spec": PRESETS["evo"],
        "words": [
            {"start": 0.0, "end": 1.0, "word": "SupercalifragilisticexpialidociousUnbelievablyLongWordThatExceedsLineLengthBudgetCompletelyNow"},
            {"start": 1.0, "end": 2.0, "word": "NormalWord"},
        ],
        "candidate_text": "MASSIVE WORD DOWNSCALING TEST",
        "aspect": "9:16",
        "duration": 2.0,
    },
    # Case 4: Aspect ratios (1:1 and 16:9)
    {
        "name": "aspect_1_1",
        "spec": PRESETS["lift"],
        "words": words[:3],
        "candidate_text": "SQUARE CANVAS TEST",
        "aspect": "1:1",
        "duration": 1.5,
    },
    {
        "name": "aspect_16_9",
        "spec": PRESETS["align"],
        "words": words[:3],
        "candidate_text": "LANDSCAPE CANVAS TEST",
        "aspect": "16:9",
        "duration": 1.5,
    },
    # Case 5: Custom prompt style overrides
    {
        "name": "prompt_custom_style",
        "spec": resolve_caption_spec(
            "clean",
            custom_style={
                "base_color": "&H00FFFFFF",
                "accent_color": "&H0000FFFF",
                "badge_box": True,
                "vertical_side": True,
                "top_banner": True,
            },
            uppercase=True,
            kinetic_pop=True,
        ),
        "words": words[:4],
        "candidate_text": "PROMPT DESIGNER MULTI-ZONE TEST",
        "aspect": "9:16",
        "duration": 2.0,
    },
]

with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    for case in adversarial_cases:
        ass_content = compile_ass(
            case["spec"],
            words=case["words"],
            start=0.0,
            end=case["duration"],
            aspect=case["aspect"],
            auto_emoji=True,
            emoji_map=EMOJI_MAP,
            auto_headline=True,
            candidate_text=case["candidate_text"],
            template="podcast",
            extract_headline=extract_headline,
        )
        ass_path = tdp / f"{case['name']}.ass"
        ass_path.write_text(ass_content, encoding="utf-8")
        escaped_ass = ass_path.resolve().as_posix().replace(":", r"\:")
        out_mp4 = tdp / f"{case['name']}.mp4"
        ass_filter = f"ass='{escaped_ass}':fontsdir='{fonts_dir}'"
        
        dims = {"9:16": "1080x1920", "1:1": "1080x1080", "16:9": "1920x1080"}[case["aspect"]]
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={dims}:d=0.25",
            "-vf", ass_filter,
            "-c:v", "libx264", "-preset", "ultrafast", str(out_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FAILED on case {case['name']}: {res.stderr}")
            exit(1)
        assert out_mp4.exists() and out_mp4.stat().st_size > 0
        print(f"Case {case['name']:25s}: OK ({out_mp4.stat().st_size} bytes)")

print("\nALL ADVERSARIAL STRESS TESTS AND FFMPEG BURNS PASSED WITH ZERO ERRORS!")
