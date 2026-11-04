import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from backend.captions.presets import PRESETS
from backend.captions.ass import compile_ass
from backend.app import EMOJI_MAP, extract_headline

words = [
    {"start": 0.0, "end": 0.4, "word": "The"},
    {"start": 0.4, "end": 0.8, "word": "biggest"},
    {"start": 0.8, "end": 1.2, "word": "mistake"}
]

# Test 1: focus preset headline & badge
content = compile_ass(
    PRESETS["focus"],
    words=words,
    start=0.0,
    end=1.5,
    aspect="9:16",
    auto_headline=True,
    candidate_text="The biggest mistake",
    extract_headline=extract_headline
)

print("=== FOCUS PRESET COMPILED ASS ===")
for line in content.splitlines()[:25]:
    print(line)

print("\n--- Assertions Check for test_multi_layer_ass_renders_headline_and_badge_boxes ---")
print("CutflowTitle in content?", "CutflowTitle" in content)
print("CutHeadline in content?", "CutHeadline" in content)
print("CutBadgeHeadline in content?", "CutBadgeHeadline" in content)
print("THE BIGGEST MISTAKE in content?", "THE BIGGEST MISTAKE" in content)
print(r"\3c&H00FFFFFF\c&H00000000 in content?", r"\3c&H00FFFFFF\c&H00000000" in content)
print("CaptionBadge in content?", "CaptionBadge" in content)

print("\n--- Assertions Check for Style: Cutflow vs Style: Caption ---")
print("Style: Cutflow, in content?", "Style: Cutflow," in content)
print("Style: Caption, in content?", "Style: Caption," in content)
