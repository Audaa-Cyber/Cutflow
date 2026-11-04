"""ASS layout compiler.

Turns a `CaptionSpec` + word timeline + aspect ratio into layered ASS events:

  layer 0   frame treatment  (letterbox bars / polaroid border / grid / scanlines / rules)
  layer 1   karaoke line backings
  layer 2   headline / hook  (kicker / badge / banner / serif / plain)
  layer 3   side rail
  layer 4   caption text runs (karaoke rolls / per-word badge runs)
  layer 2   pill backing behind the caption line

Verified anchor behaviour (probed against this exact ffmpeg build):
  * `\\an2\\pos(cx, y)` bottoms text AND `\\p1` vector drawings at (cx, y), centred.
  * `\\an8\\pos(cx, y)` tops them at (cx, y), centred.
  * `\\an7\\pos(x, y)` puts the *local origin* of a `\\p1` drawing at (x, y).
Glyph scale: ASS px â‰ˆ PIL px Ã— per-font factor, so text measurement uses PIL
at that same scaled size.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from PIL import ImageFont

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Glyph measurement calibration â€” libass draws the *same* font at a fixed
# fraction of the nominal ASS Fontsize; the fraction differs per family,
# so text measurement loads PIL at that same scaled size.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
FONT_SCALE = {
    "Montserrat": 0.62,
    "Merriweather": 0.645,
    "JetBrains Mono": 0.604,
}
FONT_FILES = {
    "Montserrat": ("Montserrat-Bold.ttf", "Montserrat-Regular.ttf"),
    "Merriweather": ("Merriweather-Bold.ttf", "Merriweather-Regular.ttf"),
    "JetBrains Mono": ("JetBrainsMono-Bold.ttf", "JetBrainsMono-Regular.ttf"),
}
FALLBACK_SCALE = 0.90
CAP_RATIO = 0.70          # capital-letter height, as a fraction of the em
DESC_RATIO = 0.23         # descent below baseline, as a fraction of the em

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

BASE = {
    "9:16": {"width": 1080, "height": 1920, "font": 92, "headline": 56, "max_chars": 22},
    "1:1": {"width": 1080, "height": 1080, "font": 82, "headline": 52, "max_chars": 26},
    "16:9": {"width": 1920, "height": 1080, "font": 78, "headline": 50, "max_chars": 40},
}
BAR_FRACTION = {"9:16": 0.135, "1:1": 0.115, "16:9": 0.115}

STYLE_FORMAT = (
    "Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, "
    "Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
)


def glyph_scale(font: str) -> float:
    return FONT_SCALE.get(font, FALLBACK_SCALE)


# â”€â”€ glyph measurement: widths equivalent to what libass will draw â”€â”€â”€â”€â”€â”€â”€â”€â”€

@lru_cache(maxsize=8)
def _font_for(font: str, px: int):
    if font in FONT_FILES:
        try:
            return ImageFont.truetype(str(FONT_DIR / FONT_FILES[font][0]), px)
        except Exception:
            pass
    for name in ("Arial Bold", "Arial Regular"):
        try:
            return ImageFont.truetype(name, px)
        except Exception:
            continue
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", px)
    except Exception:
        pass
    return ImageFont.load_default(size=px)


@lru_cache(maxsize=8192)
def measure(text: str, font: str, ass_size: int) -> float:
    """Real ASS script-pixel width of `text` at ASS font size `ass_size`."""
    px = max(1, int(round(ass_size * glyph_scale(font))))
    try:
        return float(_font_for(font, px).getlength(text))
    except Exception:
        return len(text) * ass_size * 0.55


def measure_sp(text: str, font: str, ass_size: float, letter_spacing: float = 0.0) -> float:
    return measure(text, font, max(1, int(round(ass_size)))) + max(0, len(text) - 1) * letter_spacing


# â”€â”€ small ASS helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def escape(text: str) -> str:
    return (str(text).replace("\\", "").replace("{", "(").replace("}", ")")
            .replace(",", r"\,"))


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100)) % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


EVENT_END = ass_time(35_999.99)


def alpha_of(opacity: float) -> int:
    return max(0, min(255, int(round((1.0 - max(0.0, min(1.0, opacity))) * 255))))


def _f(value: float) -> str:
    return f"{round(float(value), 2):g}"


# â”€â”€ vector drawing helpers (ASS `\p1`, local coordinates, origin top-left) â•

def subrect(x: float, y: float, w: float, h: float) -> str:
    return (f"m {_f(x)} {_f(y)} l {_f(x + w)} {_f(y)} "
            f"l {_f(x + w)} {_f(y + h)} l {_f(x)} {_f(y + h)}")


def rounded_rect(w: float, h: float, radius_fraction: float = 0.46) -> str:
    r = min(max(1.0, w * 0.499), max(1.0, h * 0.499), max(1.0, radius_fraction * h))
    k = r * 0.552
    return " ".join([
        f"m {_f(r)} 0",
        f"l {_f(w - r)} 0",
        f"b {_f(w - r + k)} 0 {_f(w)} {_f(r - k)} {_f(w)} {_f(r)}",
        f"l {_f(w)} {_f(h - r)}",
        f"b {_f(w)} {_f(h - r + k)} {_f(w - k)} {_f(h)} {_f(w - r)} {_f(h)}",
        f"l {_f(r)} {_f(h)}",
        f"b {_f(k)} {_f(h)} 0 {_f(h - k)} 0 {_f(h - r)}",
        f"l 0 {_f(r)}",
        f"b 0 {_f(k)} {_f(k)} 0 {_f(r)} 0",
    ])


def drawing_event(layer: int, start: float, end: float, style: str, *,
                  anchor: int, pos: tuple[float, float], paths, color: str,
                  opacity: float = 1.0, blur: float = 0.0) -> str:
    alpha = f"\\1a&H{alpha_of(opacity):02X}&"
    blur_tag = f"\\blur{_f(blur)}" if blur else ""
    return (
        f"Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
        f"{{\\an{anchor}\\pos({_f(pos[0])},{_f(pos[1])})\\p1\\1c{color}{alpha}"
        f"\\bord0\\shad0{blur_tag}}}" + " ".join(paths) + "{\\p0}"
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Layout geometry resolver
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@dataclass(frozen=True)
class Resolved:
    spec: "CaptionSpec"
    aspect: str
    width: int
    height: int
    font: str
    headline_font: str
    font_px: int
    headline_px: int
    spacing: float
    cap_px: float                 # capital height of the caption glyphs (ASS px)
    desc_px: float                # descent of the caption glyphs (ASS px)
    headline_cap_px: float
    caption_y: int                # bottom anchor of the caption line
    headline_y: int               # top anchor of the headline block
    bar_h: int
    max_line_px: int
    max_words: int
    max_chars: int
    rail_x: int
    rail_y: int


def resolve(spec, aspect: str) -> Resolved:
    from .spec import CaptionSpec, resolve_headline_font  # zero-cost local
    base = BASE[aspect]
    width, height = base["width"], base["height"]
    font_px = max(24, int(round(base["font"] * spec.size)))
    headline_px = max(22, int(round(base["headline"] * spec.headline_size)))
    font = spec.font
    headline_font = resolve_headline_font(spec)
    cap_px = font_px * glyph_scale(font) * CAP_RATIO
    desc_px = font_px * glyph_scale(font) * DESC_RATIO
    headline_cap_px = headline_px * glyph_scale(headline_font) * CAP_RATIO
    bar_h = int(round(height * BAR_FRACTION[aspect]))

    if spec.zone == "letterbox":
        caption_y = int(round(height - bar_h * 0.52))
        max_line_px = int(width * 0.62)
    elif spec.zone == "center":
        caption_y = int(round(height * 0.62))
        max_line_px = int(width * 0.74)
    elif spec.zone == "upper":
        caption_y = int(round(height * 0.30))
        max_line_px = int(width * 0.66)
    else:
        caption_y = int(round(height - spec.lower_margin * height))
        max_line_px = int(width * 0.78)

    if spec.zone == "letterbox":
        headline_y = int(round(bar_h * 0.42))
    elif spec.headline in ("kicker", "plain", "serif"):
        headline_y = int(round(height * 0.052))
    else:
        headline_y = int(round(height * 0.066))

    return Resolved(
        spec=spec, aspect=aspect, width=width, height=height,
        font=font, headline_font=headline_font,
        font_px=font_px, headline_px=headline_px,
        spacing=spec.letter_spacing,
        cap_px=cap_px, desc_px=desc_px, headline_cap_px=headline_cap_px,
        caption_y=caption_y, headline_y=headline_y, bar_h=bar_h,
        max_line_px=max_line_px, max_words=spec.max_words,
        max_chars=max(10, int(round(base["max_chars"] * spec.max_chars))),
        rail_x=56, rail_y=int(round(bar_h + cap_headline_x(headline_cap_px))),
    )


def cap_headline_x(v: float) -> float:
    return max(40.0, v * 2.1)


# â”€â”€ ASS style rows â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _row(name: str, font: str, size: int, *, primary: str, secondary: str,
         outline: str, back: str, bold: int = -1, italic: int = 0,
         spacing: float = 0.0, border_style: int = 1, outline_px: float = 3.5,
         shadow_px: float = 2.0, alignment: int = 2, margin_l: int = 74,
         margin_r: int = 74, margin_v: int = 10) -> str:
    return (
        f"Style: {name},{font},{size},{primary},{secondary},{outline},{back},"
        f"{bold},{italic},0,0,100,100,{_f(spacing)},0,{border_style},"
        f"{_f(outline_px)},{_f(shadow_px)},{alignment},{margin_l},{margin_r},{margin_v},1"
    )


def build_styles(res: Resolved) -> list[str]:
    spec = res.spec
    spacing = res.spacing
    bold = -1
    outline_px = max(1.2, 3.6 * spec.outline_width)
    rows: list[str] = []

    rows.append(_row("Caption", spec.font, res.font_px,
                     primary=spec.primary, secondary="&H000000FF",
                     outline=spec.outline, back="&H00000000",
                     spacing=spacing, border_style=1,
                     outline_px=outline_px, shadow_px=max(0.0, spec.shadow),
                     alignment=2))

    if spec.caption_box == "per_word":
        badge_pad = max(2.0, res.font_px * 0.115)
        for name, fill in (("CaptionBadge", spec.fill),
                           ("CaptionBadgeActive", spec.accent)):
            rows.append(_row(name, spec.font, res.font_px,
                             primary=spec.fill_text, secondary="&H000000FF",
                             outline=fill, back="&H00000000",
                             spacing=spacing, border_style=3,
                             outline_px=badge_pad, shadow_px=0.0, alignment=2))

    rows.append(_row("CutHeadline", res.headline_font, res.headline_px,
                     primary=spec.headline_color, secondary="&H000000FF",
                     outline="&H00141414", back="&H00000000",
                     spacing=spec.letter_spacing, border_style=1,
                     outline_px=max(1.4, res.headline_px * 0.06),
                     shadow_px=0.0, alignment=8))

    rows.append(_row("CutBadgeHeadline", res.headline_font, res.headline_px,
                     primary="&H00141414" if spec.headline == "badge" else spec.headline_color,
                     secondary="&H000000FF",
                     outline=spec.fill if spec.headline == "badge" else "&HFFFFFF00",
                     back="&H00000000", border_style=3,
                     outline_px=max(4.0, res.headline_px * 0.12),
                     shadow_px=0.0, alignment=8))

    rail_px = max(16, int(round(res.font_px * 0.26)))
    rows.append(_row("CutRail", spec.font, rail_px,
                     primary=spec.rail_color, secondary="&H000000FF",
                     outline="&H00141414", back="&H00000000",
                     border_style=1, outline_px=1.4, shadow_px=0.0, alignment=7))

    rows.append(_row("CutFrame", "Arial", 20,
                     primary="&H00FFFFFF", secondary="&H000000FF",
                     outline="&H00000000", back="&H00000000",
                     border_style=1, outline_px=0.0, shadow_px=0.0,
                     alignment=7, margin_l=0, margin_r=0, margin_v=0))

    # Compatibility style alias rows for unit tests and legacy consumers
    rows.append(_row("Cutflow", spec.font, res.font_px,
                     primary=spec.primary, secondary="&H000000FF",
                     outline=spec.outline, back="&H00000000",
                     spacing=spacing, border_style=1,
                     outline_px=outline_px, shadow_px=max(0.0, spec.shadow),
                     alignment=2))
    rows.append(_row("CutflowTitle", res.headline_font, res.headline_px,
                     primary=spec.headline_color, secondary="&H000000FF",
                     outline="&H00141414", back="&H00000000",
                     spacing=spec.letter_spacing, border_style=1,
                     outline_px=max(1.4, res.headline_px * 0.06),
                     shadow_px=0.0, alignment=8))
    return rows


def build_header(res: Resolved) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {res.width}\n"
        f"PlayResY: {res.height}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        f"Format: {STYLE_FORMAT}\n"
        + "\n".join(build_styles(res))
        + "\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Word timeline
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

PUNCTUATION_END = re.compile(r"[.!?,;:][\"'â€™)\]]*$")


def group_words(words: list[dict], res: Resolved) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        gap = float(word.get("start", 0.0)) - float(current[-1].get("end", 0.0)) if current else 0.0
        proposed = " ".join([str(x.get("word", "")).strip() for x in current] + [token])
        punct = bool(current and PUNCTUATION_END.search(str(current[-1].get("word", ""))))
        if current and (len(current) >= res.max_words
                        or len(proposed) > res.max_chars
                        or gap > 0.62 or punct):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def tokenized(group: list[dict], spec: "CaptionSpec", auto_emoji: bool,
              emoji_map: dict) -> list[dict]:
    tokens: list[dict] = []
    for w in group:
        text = escape(str(w.get("word", "")))
        if auto_emoji:
            norm = str(w.get("word", "")).lower().strip(".,!?;:\"'")
            emoji = emoji_map.get(norm)
            if emoji and not emoji.isspace():
                text = f"{text} {emoji}"
        if spec.uppercase:
            text = text.upper()
        tokens.append({"text": text,
                       "start": float(w.get("start", 0.0)),
                       "end": float(w.get("end", 0.0))})
    return tokens


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Frame treatment (ASS layer 0)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def frame_events(res: Resolved) -> list[str]:
    spec = res.spec
    if not spec.frame or spec.frame == "none":
        return []
    w, h = res.width, res.height
    bar = res.bar_h
    color, opacity = spec.frame_color, spec.frame_opacity
    hook = 35_999.99  # ~10 h in ASS time; ass_time() formats it inside drawing_event

    if spec.frame == "letterbox":
        return [drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                              paths=[subrect(0, 0, w, bar), subrect(0, h - bar, w, bar)],
                              color=color, opacity=opacity)]

    if spec.frame == "polaroid":
        th = max(4.0, w * 0.006)
        inset = max(24.0, w * 0.032)
        paths = [
            subrect(inset, inset, w - inset * 2, th),
            subrect(inset, h - inset - th, w - inset * 2, th),
            subrect(inset, inset, th, h - inset * 2),
            subrect(w - inset - th, inset, th, h - inset * 2),
        ]
        return [drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                              paths=paths, color=color, opacity=opacity)]

    if spec.frame == "grid":
        th = max(1.4, w * 0.0016)
        rays = [subrect(x - th / 2, 0, th, h) for x in (w // 3, 2 * w // 3)]
        rays += [subrect(0, y - th / 2, w, th) for y in (h // 3, 2 * h // 3)]
        base = [drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                              paths=rays, color=color, opacity=opacity * 0.30)]
        cl = max(30.0, w * 0.045)
        cth = max(2.0, w * 0.0024)
        off = max(18.0, w * 0.028)
        corners = []
        for x, y, dx, dy in ((off, off, 1, 1), (w - off, off, -1, 1),
                             (off, h - off, 1, -1), (w - off, h - off, -1, -1)):
            arm_x = subrect(x - cl * (dx == -1), y, cl, cth)
            arm_y = subrect(x, y - cth * (dy == -1), cth, cl)
            corners.append(arm_x)
            corners.append(arm_y)
        base.append(drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                                  paths=corners, color=color, opacity=opacity))
        return base

    if spec.frame == "scanlines":
        step = max(6, int(round(h / 110)))
        thickness = max(1.2, h * 0.0012)
        paths = [subrect(0, y, w, thickness) for y in range(0, int(h - step), step * 2)]
        return [drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                              paths=paths, color=color, opacity=opacity)]

    if spec.frame == "rules":
        th = max(2.0, h * 0.0024)
        return [drawing_event(0, 0, hook, "CutFrame", anchor=7, pos=(0, 0),
                              paths=[subrect(w * 0.14, h * 0.055, w * 0.72, th),
                                     subrect(w * 0.14, h * 0.945 - th, w * 0.72, th)],
                              color=color, opacity=opacity)]
    return []


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Headline / hook (ASS layer 2)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def headline_events(res: Resolved, headline: str, *, hook_duration: float) -> list[str]:
    spec = res.spec
    if spec.headline == "none" or not headline.strip():
        return []
    cx = res.width // 2
    text = escape(headline.upper() if spec.headline_upper else headline)
    spacing_tag = f"\\fsp{_f(spec.letter_spacing)}" if spec.letter_spacing else ""
    fade = "\\fad(220,420)"
    top = f"{fade}\\an8\\pos({cx},{int(res.headline_y)}){spacing_tag}"
    events: list[str] = []

    if spec.headline == "badge":
        # boxed hook: white fill behind the words, dark text (BorderStyle=3)
        events.append(
            f"Dialogue: 2,{ass_time(0)},{ass_time(hook_duration)},CutBadgeHeadline,,0,0,0,,"
            "{%s\\fs%d}%s " % (top, res.headline_px, text)
        )
        return events

    if spec.headline == "banner":
        pad_x = res.headline_px * 0.55
        text_width = measure_sp(text, res.headline_font, res.headline_px, spec.letter_spacing)
        bar_w = text_width + pad_x * 2
        bar_h = res.headline_cap_px * 2.05
        bar = rounded_rect(bar_w, bar_h, 0.30)
        events.append(
            drawing_event(2, 0, hook_duration, "CutFrame", anchor=8,
                          pos=(cx, res.headline_y), paths=[bar],
                          color="&H0005FFD5", opacity=0.97)
        )
        events.append(
            f"Dialogue: 3,{ass_time(0)},{ass_time(hook_duration)},CutHeadline,,0,0,0,,"
            "{%s\\c%s}%s" % (top, "&H00141610", text)
        )
        return events

    events.append(
        f"Dialogue: 2,{ass_time(0)},{ass_time(hook_duration)},CutHeadline,,0,0,0,,"
        "{%s}%s" % (top, text)
    )
    return events


def rail_event(res: Resolved, *, hook_duration: float) -> str | None:
    spec = res.spec
    if not spec.rail:
        return None
    return (
        f"Dialogue: 3,{ass_time(0)},{ass_time(hook_duration)},CutRail,,0,0,0,,"
        "{\\fad(220,420)\\an7\\pos(%d,%d)}%s" % (res.rail_x, res.rail_y, escape(spec.rail))
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Caption line (ASS layers 1 & 4)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def metrics(res: Resolved, toks: list[dict]) -> dict:
    spec = res.spec
    base = res.font_px
    text = " ".join(t["text"] for t in toks)
    width = measure_sp(text, spec.font, base, spec.letter_spacing)
    size = base
    step = max(1, int(round(base * 0.01)))
    while width > res.max_line_px and (size - step) >= int(base * 0.58):
        size -= step
        width = measure_sp(text, spec.font, size, spec.letter_spacing)
    widths = [measure_sp(t["text"], spec.font, size, spec.letter_spacing) for t in toks]
    space = measure(" ", spec.font, size)
    total = sum(widths) + space * max(0, len(toks) - 1)
    return {"size": size, "widths": widths, "space": space,
            "total": total, "left": res.width / 2 - total / 2}


def _slices(toks: list[dict], line_start: float, line_end: float,
            wants_karaoke: bool) -> list[dict]:
    if not wants_karaoke:
        return [{"index": None, "start": line_start, "end": line_end}]
    out: list[dict] = []
    for i in range(len(toks)):
        s = max(line_start, toks[i]["start"])
        if i + 1 < len(toks):
            e = max(s + 0.12, min(line_end, toks[i + 1]["start"]))
        else:
            e = max(s + 0.12, min(line_end + 0.18, toks[i]["end"] + 0.18))
        if e <= s:
            continue
        out.append({"index": i, "start": s, "end": e})
    return out


def caption_events(res: Resolved, toks: list[dict], *,
                   auto_emoji: bool, emoji_map: dict,
                   start: float, end: float) -> list[str]:
    """Caption line events: pill/underline/marker backing + text runs."""
    spec = res.spec
    events: list[str] = []
    line_start = max(0.0, toks[0]["start"] - start)
    line_end = min(end, toks[-1]["end"] + 0.16) - start
    if line_end <= line_start:
        return events

    m = metrics(res, toks)
    cx = res.width // 2
    wants_karaoke = spec.karaoke and len(toks) > 1
    slices = _slices(toks, line_start, line_end, wants_karaoke)

    def line_pos() -> str:
        return f"\\pos({cx},{res.caption_y})"

    def fs_tag() -> str:
        return f"\\fs{m['size']}" if m['size'] != res.font_px else ""

    def fsp_tag() -> str:
        return f"\\fsp{_f(spec.letter_spacing)}" if spec.letter_spacing else ""

    def blur_tag() -> str:
        return f"\\blur{_f(spec.glow)}" if spec.glow else ""

    # (a) pill behind the whole caption line, drawn once
    if spec.caption_box == "pill":
        pad_x = spec.box_pad_x * m['size']
        pad_y = max(4.0, m['size'] * 0.22)
        height = res.cap_px + res.desc_px + pad_y
        path = rounded_rect(m['total'] + pad_x * 2, height, spec.box_radius)
        events.append(
            drawing_event(1, line_start, line_end, "CutFrame", anchor=2,
                          pos=(cx, res.caption_y), paths=[path],
                          color=spec.fill, opacity=spec.fill_opacity,
                          blur=spec.glow * 0.5)
        )

    # (b) caption text runs â€” one per karaoke slice
    for sl in slices:
        s0, s1 = sl["start"], sl["end"]
        active = sl["index"]
        runs: list[str] = []

        for j, tok in enumerate(toks):
            is_active = wants_karaoke and active is not None and j == active
            spoken = wants_karaoke and active is not None and j < active
            upcoming = wants_karaoke and active is not None and j > active

            if spec.caption_box == "per_word":
                ref = "CaptionBadgeActive" if is_active else "CaptionBadge"
                badge_outline = spec.accent if is_active else spec.fill
                runs.append(f"{{\\r{ref}" + (fs_tag() or f"\\fs{res.font_px}") + f"\\3c{badge_outline}\\c{spec.fill_text}" + "}")
                if is_active and spec.active_pop:
                    runs.append("{\\fscx114\\fscy114}")
                runs.append(tok["text"])
                if is_active and spec.active_pop:
                    runs.append("{\\fscx100\\fscy100}")
                if j < len(toks) - 1:
                    runs.append(" ")
                continue

            # speaker states for non-boxed presets
            if upcoming:
                color = spec.upcoming
            elif is_active and spec.active == "accent":
                color = spec.accent
            elif is_active and spec.active == "glow":
                color = spec.accent
            elif is_active and spec.active in ("bracket", "underline", "marker"):
                color = spec.primary
            elif not wants_karaoke and spec.active == "accent" and j == len(toks) - 1:
                color = spec.accent
            else:
                color = spec.primary

            scale_in = tag_out = ""
            if is_active and spec.active_pop and spec.active not in ("underline", "marker"):
                scale_in, tag_out = "{\\fscx114\\fscy114}", "{\\fscx100\\fscy100}"
            if is_active and spec.active == "bracket":
                tok = {**tok, "text": f"{spec.bracket[0]}{tok['text']}{spec.bracket[-1]}"}
            if is_active and spec.active in ("underline", "marker"):
                left = m["left"] + sum(m["widths"][:j]) + m["space"] * j
                events.append(_word_backing(res, m, left, m["widths"][j],
                                            is_active=True, start=s0, end=s1))
            runs.append(f"{{\\c{color}}}")
            if scale_in:
                runs.append(scale_in)
            runs.append(tok["text"])
            if tag_out:
                runs.append(tag_out)
            runs.append(" " if j < len(toks) - 1 else "")

        text = "".join(runs).strip()
        events.append(
            f"Dialogue: 4,{ass_time(s0)},{ass_time(s1)},Caption,,0,0,0,,"
            f"{{\\an2{line_pos()}{fs_tag()}{fsp_tag()}{blur_tag()}}}{text}"
        )
    return events


def _word_backing(res: Resolved, m: dict, left: float, width: float, *,
                  is_active: bool, start: float, end: float) -> str | None:
    spec = res.spec
    if spec.active == "marker":
        pad = m["size"] * 0.16
        height = res.cap_px + res.desc_px * 0.25
        return drawing_event(1, start, end, "CutFrame", anchor=2,
                             pos=(left - pad + width / 2, res.caption_y),
                             paths=[rounded_rect(width + pad * 2, height, 0.24)],
                             color=spec.fill or spec.accent, opacity=spec.fill_opacity)
    if spec.active == "underline":
        y = res.caption_y + res.cap_px * 0.42
        h = max(2.4, m["size"] * 0.10)
        return drawing_event(1, start, end, "CutFrame", anchor=7,
                             pos=(left, y),
                             paths=[subrect(0, 0, width, h)], color=spec.accent,
                             opacity=0.95)
    return None


EVENT_END_TIME = ass_time(35_999.99)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Top-level compiler entry point
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def compile_ass(spec, *, words: list[dict], start: float, end: float,
                aspect: str, auto_emoji: bool = False, emoji_map: dict | None = None,
                auto_headline: bool = True, headline_text: str | None = None,
                hook_duration: float | None = None, candidate_text: str = "",
                template: str = "podcast", extract_headline=None) -> str:
    """Compile one caption preset into an ASS script for a candidate clip."""
    emoji_map = emoji_map or {}
    if spec.headline != "none" and hook_duration is None:
        hook_duration = min(max(1.2, (end - start) * 0.42), 4.0)
    elif hook_duration is None:
        hook_duration = max(1.2, (end - start) * 0.40)

    res = resolve(spec, aspect)
    visible = [w for w in words if float(w["end"]) > start and float(w["start"]) < end]
    events: list[str] = frame_events(res)

    if auto_headline and (visible or candidate_text or headline_text):
        hook_text = headline_text
        if not hook_text and extract_headline is not None:
            hook_text = extract_headline(candidate_text or visible, template)
        if not hook_text:
            hook_text = (spec.headline_text or "KEY MOMENT")
        events.extend(headline_events(res, hook_text, hook_duration=hook_duration))

    rail = rail_event(res, hook_duration=hook_duration)
    if rail:
        events.append(rail)

    for group in group_words(visible, res):
        toks = tokenized(group, spec, auto_emoji, emoji_map)
        if not toks:
            continue
        events.extend(caption_events(res, toks, start=start, end=end,
                                     auto_emoji=auto_emoji, emoji_map=emoji_map))

    return build_header(res) + "\n" + "\n".join(events) + "\n"
