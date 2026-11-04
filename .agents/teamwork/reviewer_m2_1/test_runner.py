import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tempfile
from backend.app import CAPTION_STYLES, write_ass, parse_caption_prompt

def test_styles_inspection():
    print("=== INSPECTING ALL 18 CAPTION STYLES ===")
    for k, v in sorted(CAPTION_STYLES.items()):
        print(f"{k:10s} base={v['base_color']} outline_c={v['outline_color']} accent={v['accent_color']} "
              f"back={v['back_color']} out={v['outline']} sh={v['shadow']} gl={v['glow']} "
              f"pop={v['kinetic_pop']} box={v['badge_box']} pill={v['pill']} ban={v['top_banner']} "
              f"side={v['vertical_side']}")

def test_render_all_styles():
    print("\n=== RENDERING ALL 18 STYLES ACROSS 3 RATIOS ===")
    words = [
        {"start": 0.0, "end": 0.4, "word": "The"},
        {"start": 0.4, "end": 0.8, "word": "quick"},
        {"start": 0.8, "end": 1.2, "word": "brown"},
        {"start": 1.2, "end": 1.6, "word": "fox"},
    ]
    ratios = ["9:16", "1:1", "16:9"]
    with tempfile.TemporaryDirectory() as td:
        count = 0
        for style_name in CAPTION_STYLES:
            for ratio in ratios:
                out_path = Path(td) / f"{style_name}_{ratio.replace(':', '_')}.ass"
                write_ass(out_path, words, 0.0, 2.0, ratio, caption_style=style_name, auto_headline=True)
                assert out_path.exists(), f"File {out_path} not created"
                content = out_path.read_text(encoding="utf-8")
                assert "Style: Cutflow," in content, "Missing Cutflow style definition"
                assert "PlayRes" in content, "Missing PlayRes in ASS script info"
                count += 1
        print(f"Successfully generated {count} ASS files (18 styles x 3 ratios).")

def test_adversarial_custom_styles():
    print("\n=== ADVERSARIAL STRESS TEST: SPARSE & DEFENSIVE CUSTOM STYLES ===")
    words = [{"start": 0.0, "end": 0.5, "word": "Adversarial"}, {"start": 0.5, "end": 1.0, "word": "Test"}]
    test_cases = [
        ("empty_dict", {}),
        ("none_values", {"base_color": None, "outline_color": None, "accent_color": None, "back_color": None, "badge_box": None}),
        ("spec_keys_only", {"primary": "&H00112233", "outline": "&H00445566", "accent": "&H00778899", "upcoming": "&H00AABBCC", "fill": "&H00DDEEFF"}),
        ("badge_box_true", {"badge_box": True}),
        ("pill_true", {"pill": True}),
        ("vertical_side_true", {"vertical_side": True}),
        ("top_banner_true", {"top_banner": True}),
        ("unknown_font", {"font": "SomeRandomComicSans"}),
        ("empty_words", []),
    ]
    with tempfile.TemporaryDirectory() as td:
        for name, custom_dict in test_cases:
            out_path = Path(td) / f"{name}.ass"
            w = words if name != "empty_words" else []
            write_ass(out_path, w, 0.0, 2.0, "9:16", custom_style=custom_dict if name != "empty_words" else None)
            assert out_path.exists()
            content = out_path.read_text(encoding="utf-8")
            assert "Style: Cutflow," in content
            print(f"PASS: {name}")

if __name__ == "__main__":
    test_styles_inspection()
    test_render_all_styles()
    test_adversarial_custom_styles()
    print("\nALL STRESS TESTS PASSED SUCCESSFULLY!")
