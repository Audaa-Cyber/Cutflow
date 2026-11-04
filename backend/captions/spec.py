"""Declarative caption style specs.

Every caption preset is a single `CaptionSpec` describing typography,
colors, geometry, boxes, active-word decoration, headline treatment,
frame treatment and side rail. The ASS compiler (`ass.py`) turns this
into layered ASS events, so a preset declares *what it looks like*,
never *how to render it*.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Optional

# ── ASS colour tokens (&HAABBGGRR, alpha 0 = opaque) ═════════════════════
WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
CREAM = "&H00F7F4EC"
DARK_PAPER = "&H00120F0E"

FONTS_SUPPORTED = ("Montserrat", "Merriweather", "JetBrains Mono")
DEFAULT_FONT = "Montserrat"


@dataclass(frozen=True)
class CaptionSpec:
    key: str
    label: str
    description: str

    # ─ typography ────────────────────────────────────────────────────────
    font: str = DEFAULT_FONT
    headline_font: Optional[str] = None      # falls back to `font`
    uppercase: bool = False
    karaoke: bool = True                     # word-by-word roll
    letter_spacing: float = 0.0              # ASS `\fsp` px between glyphs
    size: float = 1.0                        # × aspect base font size
    headline_size: float = 1.0               # × aspect base headline size
    outline_width: float = 1.0               # × base outline thickness
    shadow: float = 2.0                      # ASS `\shad` px
    glow: float = 0.0                        # ASS `\blur` px

    # ─ colours ───────────────────────────────────────────────────────────
    primary: str = WHITE
    accent: str = "&H00D5FF5F"
    upcoming: str = "&H00999999"
    outline: str = "&H00141414"
    fill: str = WHITE                        # box / pill / banner fill
    fill_text: str = BLACK                   # text drawn on `fill`
    fill_opacity: float = 1.0                # 1 opaque … 0.3 frosted

    # ─ geometry ──────────────────────────────────────────────────────────
    zone: str = "lower"                      # lower | center | upper | letterbox
    lower_margin: float = 0.17               # fraction of canvas height
    max_words: int = 3
    max_chars: float = 1.0                   # × per-aspect char budget

    # ─ caption container + active-word decoration ───────────────────────
    caption_box: str = "none"                # none | per_word | pill
    box_radius: float = 0.46                 # corner radius × box height
    box_pad_x: float = 0.32                  # × font size, horizontal
    active: str = "accent"                   # accent | box | bracket | underline | marker
    active_pop: bool = True
    bracket: str = "[ ]"

    # ─ headline / hook ───────────────────────────────────────────────────
    headline: str = "plain"                  # none | plain | badge | banner | serif | kicker
    headline_text: Optional[str] = None
    headline_upper: bool = True
    headline_color: str = WHITE

    # ─ frame & rail ──────────────────────────────────────────────────────
    frame: str = "none"                      # none | letterbox | polaroid | grid | scanlines | rules
    frame_color: str = CREAM
    frame_opacity: float = 1.0
    rail: Optional[str] = None
    rail_color: str = WHITE

    # free-form extras (prompt designer may add hints)
    extras: dict = field(default_factory=dict)

    def with_overrides(self, **overrides) -> "CaptionSpec":
        """Copy with selected known fields replaced; unknown keys → extras."""
        known = {f.name for f in fields(self.__class__)}
        base: dict = {}
        extra: dict = {}
        for key, value in overrides.items():
            if not key in known:
                continue
            base[key] = value
        for key, value in overrides.items():
            if key not in known and value is not None:
                extra[key] = value
        base["extras"] = {**self.extras, **extra}
        return replace(self, **base)


def resolve_headline_font(spec: "CaptionSpec") -> str:
    return spec.headline_font or spec.font
