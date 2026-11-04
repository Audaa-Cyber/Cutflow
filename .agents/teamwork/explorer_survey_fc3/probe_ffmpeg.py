import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

import subprocess
import tempfile
from backend.captions.presets import PRESETS
from backend.captions.ass import compile_ass
from backend.app import FONTS_DIR

words = [
    {"start": 0.1, "end": 0.4, "word": "Testing"},
    {"start": 0.4, "end": 0.7, "word": "Caption"},
    {"start": 0.7, "end": 1.0, "word": "AI"},
    {"start": 1.0, "end": 1.4, "word": "Full-Canvas"},
    {"start": 1.4, "end": 1.8, "word": "Workflow"}
]

errors = []
warnings = []

with tempfile.TemporaryDirectory() as td:
    fonts_dir = FONTS_DIR.resolve().as_posix().replace(":", r"\:")
    
    for aspect in ["9:16", "1:1", "16:9"]:
        dim = {"9:16": "1080x1920", "1:1": "1080x1080", "16:9": "1920x1080"}[aspect]
        for style_key, spec in PRESETS.items():
            sub_path = Path(td) / f"{style_key}_{aspect.replace(':', '-')}.ass"
            try:
                ass_text = compile_ass(
                    spec,
                    words=words,
                    start=0.0,
                    end=2.0,
                    aspect=aspect,
                    auto_headline=True,
                    candidate_text="Testing Full-Canvas Captions Hook",
                    auto_emoji=True,
                    emoji_map={"ai": "🤖", "testing": "⚡"}
                )
            except Exception as e:
                errors.append(f"compile_ass failed for {style_key} ({aspect}): {e}")
                continue
            
            sub_path.write_text(ass_text, encoding="utf-8")
            out_mp4 = Path(td) / f"out_{style_key}_{aspect.replace(':', '-')}.mp4"
            ass_path = sub_path.resolve().as_posix().replace(":", r"\:")
            ass_filter = f"ass='{ass_path}':fontsdir='{fonts_dir}'"
            
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={dim}:d=0.2:r=25",
                "-vf", ass_filter,
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                str(out_mp4)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                errors.append(f"FFmpeg failed for {style_key} ({aspect}): rc={res.returncode}, stderr={res.stderr}")
            else:
                if res.stderr.strip():
                    warnings.append(f"{style_key} ({aspect}) warnings:\n{res.stderr.strip()}")

print(f"Tested {len(PRESETS) * 3} combinations.")
print(f"Errors count: {len(errors)}")
print(f"Warnings count: {len(warnings)}")
if errors:
    print("ERRORS:")
    for err in errors[:10]:
        print(" ", err)
if warnings:
    print("WARNINGS:")
    for warn in warnings[:10]:
        print(" ", warn)
