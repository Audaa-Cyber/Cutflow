import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tempfile
import subprocess
import os
from backend.captions.presets import PRESETS
from backend.captions.ass import compile_ass, resolve
from backend.app import EMOJI_MAP, extract_headline, resolve_caption_spec, write_ass

print(f"Total presets in PRESETS: {len(PRESETS)}")
assert len(PRESETS) == 18, f"Expected 18 presets, found {len(PRESETS)}"

fonts_dir = (REPO_ROOT / "backend" / "assets" / "fonts").resolve().as_posix().replace(":", r"\:")
print(f"Using fonts_dir: {fonts_dir}")

words = [
    {"start": 0.0, "end": 0.4, "word": "Full"},
    {"start": 0.4, "end": 0.8, "word": "canvas"},
    {"start": 0.8, "end": 1.2, "word": "subtitles"},
    {"start": 1.2, "end": 1.6, "word": "viral"},
    {"start": 1.6, "end": 2.0, "word": "growth"},
]

with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    # 1. Test all 18 presets
    for key, spec in PRESETS.items():
        ass = compile_ass(
            spec, words=words, start=0.0, end=2.0, aspect="9:16",
            auto_emoji=True, emoji_map=EMOJI_MAP, auto_headline=True,
            candidate_text="THE SECRET TO GROWTH", template="podcast",
            extract_headline=extract_headline,
        )
        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "Dialogue:" in ass

        ass_path = tdp / f"{key}.ass"
        ass_path.write_text(ass, encoding="utf-8")
        out_mp4 = tdp / f"{key}.mp4"
        escaped_ass = ass_path.resolve().as_posix().replace(":", r"\:")

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=0.3",
            "-vf", f"ass='{escaped_ass}':fontsdir='{fonts_dir}'",
            "-c:v", "libx264", "-preset", "ultrafast", str(out_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed on {key}: {res.stderr}")
        assert out_mp4.exists() and out_mp4.stat().st_size > 1000, f"File empty or missing for {key}"
    print("All 18 presets compiled and burned cleanly via FFmpeg!")

    # 2. Test Multi-Zone features specifically:
    # Zone 1: Hook Headline / Banner
    lift_spec = PRESETS["lift"]
    lift_ass = compile_ass(lift_spec, words=words, start=0.0, end=2.0, aspect="9:16", candidate_text="THE SECRET TO GROWTH", extract_headline=extract_headline)
    assert "CutHeadline" in lift_ass
    assert "&H0005FFD5" in lift_ass  # emerald banner fill
    print("Zone 1 (Banner & Headline) verified!")

    # Zone 2: Kinetic Dialogue with word bounding-box pills and color pop
    focus_spec = PRESETS["focus"]
    focus_ass = compile_ass(focus_spec, words=words, start=0.0, end=2.0, aspect="9:16")
    assert "CaptionBadge" in focus_ass
    assert r"\fscx114\fscy114" in focus_ass  # kinetic pop
    print("Zone 2 (Pills & Pop) verified!")

    # Zone 3: Frame / Rails
    align_spec = PRESETS["align"]
    align_ass = compile_ass(align_spec, words=words, start=0.0, end=2.0, aspect="9:16")
    assert "CutFrame" in align_ass
    stack_spec = PRESETS["stack"]
    stack_ass = compile_ass(stack_spec, words=words, start=0.0, end=2.0, aspect="9:16")
    assert "CutRail" in stack_ass
    print("Zone 3 (Frame & Rails) verified!")

    # Zone 4: Safe Margins
    resolved_916 = resolve(focus_spec, "9:16")
    assert resolved_916.caption_y <= 1920 * (1.0 - focus_spec.lower_margin + 0.02)
    print("Zone 4 (Safe Margins) verified!")

    # 3. Test Fallback Candidate (empty words)
    fallback_ass = compile_ass(focus_spec, words=[], start=0.0, end=2.0, aspect="9:16", candidate_text="TOPIC HIGHLIGHT")
    assert "Dialogue:" in fallback_ass
    fb_path = tdp / "fallback.ass"
    fb_path.write_text(fallback_ass, encoding="utf-8")
    fb_out = tdp / "fallback.mp4"
    escaped_fb = fb_path.resolve().as_posix().replace(":", r"\:")
    fb_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=0.3",
        "-vf", f"ass='{escaped_fb}':fontsdir='{fonts_dir}'",
        "-c:v", "libx264", "-preset", "ultrafast", str(fb_out)
    ]
    fb_res = subprocess.run(fb_cmd, capture_output=True, text=True)
    assert fb_res.returncode == 0, f"Fallback burn failed: {fb_res.stderr}"
    assert fb_out.exists() and fb_out.stat().st_size > 1000
    print("Fallback clip burn verified!")

    # 4. Test write_ass compatibility facade
    compat_ass_path = tdp / "compat.ass"
    write_ass(compat_ass_path, words, 0.0, 2.0, "9:16", caption_style="evo", auto_headline=True, candidate_text="COMPAT TEST")
    compat_content = compat_ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in compat_content
    assert "Caption" in compat_content
    print("Legacy write_ass facade verified!")

print("INDEPENDENT EXECUTION AND AUDIT COMPLETED SUCCESSFULLY!")
