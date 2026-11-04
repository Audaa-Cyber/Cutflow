"""18 caption presets expressed as declarative `CaptionSpec`s.

Each preset is a distinct layout/typography/treatment combination, not a
colour tint of a shared layout. Keys match the ids used by the frontend
cards, the `caption_style` form field and `/api/caption-styles`.
"""

from __future__ import annotations

from .spec import BLACK, CREAM, DARK_PAPER, WHITE, CaptionSpec

PRESETS: dict[str, CaptionSpec] = {}


def add(*, key: str, label: str, description: str, **kw) -> None:
    PRESETS[key] = CaptionSpec(key=key, label=label, description=description, **kw)


# ── Captions.ai flagship layouts ═════════════════════════════════════════

add(key="focus",
    label="Focus · Inverted Dialogue Badge Boxes",
    description="Word-sized inverted badge boxes, top hook headline, accent spoken word.",
    uppercase=True, zone="lower", lower_margin=0.17, size=0.94,
    caption_box="per_word", active="box",
    accent="&H0000FFFF",
    headline="badge",
    outline_width=0.9, shadow=1.5)

add(key="linen",
    label="Linen · Editorial Serif Hook & Subtitles",
    description="Serif dialogue, editorial rule, serif hook headline, airy margin.",
    font="Merriweather", headline_font="Merriweather",
    zone="lower", lower_margin=0.21, size=0.98, letter_spacing=0.5,
    primary=CREAM, accent="&H0000C4A8",
    headline="serif", headline_color=CREAM,
    outline_width=0.7, shadow=1.5,
    frame="rules", frame_color=CREAM)

add(key="evo",
    label="Evo · Frosted Glass Gradient Pill & Cyan Pop",
    description="Frosted translucent rounded pill, cyan pop on the spoken word, glow.",
    zone="lower", lower_margin=0.17, size=1.0,
    caption_box="pill", box_radius=0.48, box_pad_x=0.46,
    fill="&H221832", fill_opacity=0.34, fill_text=WHITE,
    accent="&H0000FFFF", upcoming="&H00A9A9A9",
    outline="&H00161420", outline_width=1.2, shadow=1.5, glow=1.1,
    headline="plain")

add(key="lift",
    label="Lift · Curved Header Banner & Emerald Pop",
    description="Filled rounded header banner, emerald spoken word with underline.",
    uppercase=True, zone="lower", lower_margin=0.16, size=0.96,
    accent="&H0005FFD5", active="underline",
    headline="banner", headline_color="&H00141610",
    outline="&H00101812", outline_width=1.15)

add(key="stack",
    label="Stack · Brutalist Technical Box & Grid",
    description="Monospace, bracketed spoken words, grid frame, technical rail.",
    font="JetBrains Mono", headline_font="JetBrains Mono",
    uppercase=True, zone="lower", lower_margin=0.18, size=0.86,
    letter_spacing=0.4, active="bracket",
    accent="&H0000FFFF", upcoming="&H00777777",
    headline="kicker", frame="grid", frame_color="&H0000FFFF",
    rail="CUTFLOW // MOTION GRAPHICS", rail_color="&H0000FFFF")

add(key="align",
    label="Align · Polaroid Frame & Letterbox Dialogue",
    description="Cinematic letterbox bars, polaroid frame, letter-spaced dialogue.",
    zone="letterbox", size=0.84, letter_spacing=2.2,
    active="underline", accent=WHITE, upcoming="&H00B4B4B4",
    headline="kicker",
    frame="letterbox", frame_color=BLACK, frame_opacity=1.0,
    extras={"polaroid": True})

# ── viral kinetic styles ═════════════════════════════════════════════════

add(key="prime",
    label="Prime · Trending Viral Active",
    description="Clean viral subtitles, bright highlighted spoken word.",
    zone="lower", lower_margin=0.17, size=1.0,
    accent="&H00FFFA93", active="accent",
    headline="kicker")

add(key="impact",
    label="Impact II · Bold High-Contrast",
    description="Heavy two-word caption, thick outline, yellow punch word.",
    uppercase=True, max_words=2, zone="lower", lower_margin=0.15, size=1.18,
    accent="&H0000FFFF", active="accent",
    headline="plain",
    outline=BLACK, outline_width=1.7, shadow=3.0)

add(key="paper",
    label="Paper II · Editorial Pill",
    description="Cream solid pill behind the line, dark editorial text, orange pop.",
    zone="lower", lower_margin=0.18, size=0.96,
    caption_box="pill", box_radius=0.44, box_pad_x=0.38,
    fill="&H00F7ECE7", fill_text=DARK_PAPER, fill_opacity=0.96,
    accent="&H002ACBC7", active="accent",
    headline="serif", headline_font="Merriweather", headline_color=DARK_PAPER)

add(key="elevate",
    label="Elevate · Luxury Minimal",
    description="Letterspaced small caps, hairline rules, understated underline.",
    uppercase=True, zone="lower", lower_margin=0.22, size=0.82,
    letter_spacing=2.0, active="underline",
    primary="&H00F2F2F2", accent="&H00009C63", upcoming="&H00666666",
    headline="kicker", frame="rules", frame_color="&H00788C99",
    outline_width=0.5, shadow=1.0)

add(key="pop",
    label="Pop · Bouncy Neon Kinetic",
    description="Bouncy caption, underlined neon spoken word, playful glow.",
    zone="lower", lower_margin=0.17, size=1.0,
    accent="&H0000AEAA", active="underline",
    outline="&H001A1024", outline_width=1.3, shadow=3.0, glow=1.3,
    headline="plain")

add(key="y2k",
    label="Y2K · Cyberpunk Neon",
    description="Cyber grid + scanline frame, marker-highlighted magenta word.",
    uppercase=True, zone="center", size=0.94,
    accent="&H000051FF", active="marker",
    fill="&H000051FF", fill_opacity=0.30,
    headline="kicker",
    frame="scanlines", frame_color="&H000051FF", frame_opacity=0.30,
    rail="Y2K // SIGNAL", rail_color="&H000051FF",
    outline=BLACK, outline_width=1.4, shadow=3.0, glow=1.6)

add(key="chalk",
    label="Chalk · Tutorial Sketch Highlighter",
    description="Marker highlight on the spoken word, hairline rules, soft serif.",
    font="Merriweather", headline_font="Merriweather",
    zone="lower", lower_margin=0.20, size=0.90, letter_spacing=0.3,
    accent="&H0000D4FD", active="marker",
    fill="&H0000D4FD", fill_opacity=0.30,
    headline="kicker",
    frame="rules", frame_color="&H0000D4FD", frame_opacity=0.55,
    outline_width=0.9, shadow=1.5)

# ── creator & clean presets ══════════════════════════════════════════════

add(key="clean",
    label="Clean Subtitles",
    description="Minimal white dialogue, subtle outline, no karaoke motion.",
    zone="lower", lower_margin=0.17, size=0.92,
    karaoke=False, active="none",
    accent="&H0066F4C6",
    headline="none",
    outline_width=0.85, shadow=2.0)

add(key="pulse",
    label="Pulse Viral (Karaoke)",
    description="Word-by-word karaoke, mint spoken word, grey upcoming.",
    zone="lower", lower_margin=0.17, size=0.96,
    karaoke=True, active="accent",
    accent="&H0066F4C6",
    headline="none")

add(key="glow",
    label="Neon Cyber Glow",
    description="Karaoke captions with a soft neon glow trail on spoken words.",
    zone="lower", lower_margin=0.17, size=0.96,
    karaoke=True, active="accent",
    accent="&H0000F466",
    outline="&H00302A16", shadow=3.0, glow=1.8,
    headline="none")

add(key="hormozi",
    label="Hormozi Gold Pop",
    description="Loud uppercase, deep black outline, golden punch word.",
    uppercase=True, max_words=2, zone="lower", lower_margin=0.14, size=1.18,
    accent="&H0000E6FF", active="accent",
    headline="none",
    outline=BLACK, outline_width=1.8, shadow=3.0)

add(key="karaoke",
    label="Dynamic Karaoke Pill",
    description="Translucent pill behind the line, lime spoken word, warm shadow.",
    zone="lower", lower_margin=0.17, size=0.96,
    caption_box="pill", box_radius=0.48, box_pad_x=0.42,
    fill="&H00131A1B", fill_opacity=0.42, fill_text=WHITE,
    karaoke=True, active="accent", accent="&H00D5FF5F",
    headline="none",
    outline="&H00181A14", shadow=2.5)


def get(key: str) -> CaptionSpec | None:
    return PRESETS.get(key)


CAPTION_STYLE_ORDER = list(PRESETS.keys())
