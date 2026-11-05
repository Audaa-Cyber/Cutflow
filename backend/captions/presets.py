"""18 caption presets expressed as declarative 4-layer `CaptionSpec` recipes (Phase 4).

Every preset is a complete, self-contained visual recipe combining:
  1. Typography & Layout Geometry (curated creator font, uppercase, tracking, tilt)
  2. Kinetic Generator & Spring Curve (Pop/Bounce, Word Wave, or Elastic Pill Glider)
  3. Multi-Pass Shader Stack (active gradients, concentric strokes, ambient glow & shadows)
  4. Frame Treatments & Background Highlights (curved banners, pills, letterboxes, rules)
"""

from __future__ import annotations

from .spec import BLACK, CREAM, DARK_PAPER, WHITE, CaptionSpec

PRESETS: dict[str, CaptionSpec] = {}


def add(*, key: str, label: str, description: str, **kw) -> None:
    PRESETS[key] = CaptionSpec(key=key, label=label, description=description, **kw)


# ── Curated Flagship Creator Archetypes ───────────────────────────────────

add(key="hormozi",
    label="Hormozi Punch · Komika Heavy Strike",
    description="High-energy creator punch in Komika Axis with dynamic -2.5° tilt, dual concentric stroke, and golden gradient pop.",
    font="Komika Axis", headline_font="Komika Axis",
    uppercase=True, max_words=2, zone="lower", lower_margin=0.14, size=1.16,
    kinetic_mode="pop", spring_tension=300.0, spring_friction=13.0,
    tilt_deg=-2.5,
    outer_stroke_width=2.4, outer_stroke_color="#000000",
    inner_stroke_width=0.7, inner_stroke_color="#FFFFFF",
    active_gradient=("#FFE600", "#FF8400"),
    shadow_blur=6.0, shadow_y=4.0, shadow_color="rgba(0, 0, 0, 0.90)",
    accent="&H0000E6FF", active="accent",
    headline="none",
    outline=BLACK, outline_width=2.0, shadow=3.0)

add(key="impact",
    label="Impact II · Anton Massive Punch",
    description="Massive high-contrast 2-word punch in Anton with heavy obsidian stroke, electric lime gradient, and pop overshoot.",
    font="Anton", headline_font="Anton",
    uppercase=True, max_words=2, zone="lower", lower_margin=0.15, size=1.22,
    kinetic_mode="pop", spring_tension=320.0, spring_friction=14.0,
    tilt_deg=1.5,
    outer_stroke_width=2.8, outer_stroke_color="#000000",
    active_gradient=("#D5FF5F", "#A6FF00"),
    shadow_blur=12.0, shadow_y=6.0, shadow_color="rgba(0, 0, 0, 0.85)",
    accent="&H0000FFFF", active="accent",
    headline="plain",
    outline=BLACK, outline_width=2.2, shadow=3.0)

add(key="glow",
    label="Cyberpunk · Syne Neon Bloom",
    description="Futuristic display typography in Syne with wide neon cyan bloom glow, obsidian outline, and wave motion.",
    font="Syne", headline_font="Syne",
    uppercase=True, zone="lower", lower_margin=0.17, size=1.04, letter_spacing=1.2,
    kinetic_mode="wave", spring_tension=240.0, spring_friction=16.0,
    outer_stroke_width=1.8, outer_stroke_color="#0B0D13",
    glow_blur=22.0, glow_color="#00F5D4",
    active_gradient=("#B0FFEA", "#00F5D4"),
    shadow_blur=8.0, shadow_y=3.0, shadow_color="rgba(0, 0, 0, 0.80)",
    accent="&H0000F466", active="accent",
    outline="&H00302A16", shadow=3.0,
    headline="none")

add(key="prime",
    label="Prime · The Bold Font Viral Pop",
    description="Clean viral TikTok subtitles in The Bold Font with punchy concentric stroke and vibrant lemon-to-coral active gradient.",
    font="The Bold Font", headline_font="The Bold Font",
    uppercase=True, zone="lower", lower_margin=0.17, size=1.10, max_words=2,
    kinetic_mode="pop", spring_tension=270.0, spring_friction=15.0,
    outer_stroke_width=2.2, outer_stroke_color="#10110F",
    active_gradient=("#FFF500", "#FF6B6B"),
    shadow_blur=6.0, shadow_y=3.0, shadow_color="rgba(0, 0, 0, 0.80)",
    accent="&H00FFFA93", active="accent",
    headline="kicker")

add(key="align",
    label="Align · Bebas Neue Letterbox",
    description="Cinematic letterbox bars with Bebas Neue wide letterspacing, amber champagne active gradient, and staggered wave motion.",
    font="Bebas Neue", headline_font="Bebas Neue",
    uppercase=True, zone="letterbox", size=1.12, letter_spacing=2.6, max_words=3,
    kinetic_mode="wave", spring_tension=210.0, spring_friction=19.0,
    outer_stroke_width=1.2, outer_stroke_color="#141414",
    active_gradient=("#FFF3B0", "#E09F3E"),
    active="underline", accent=WHITE, upcoming="&H00B4B4B4",
    headline="kicker",
    frame="letterbox", frame_color=BLACK, frame_opacity=1.0,
    extras={"polaroid": True})

add(key="pop",
    label="Pop · Bouncy Neon Kinetic",
    description="Playful kinetic bouncing typography in The Bold Font with dual black/magenta concentric stroke and neon bloom glow.",
    font="The Bold Font", headline_font="The Bold Font",
    uppercase=True, zone="lower", lower_margin=0.17, size=1.06,
    kinetic_mode="pop", spring_tension=290.0, spring_friction=14.0,
    outer_stroke_width=2.4, outer_stroke_color="#120A1E",
    inner_stroke_width=0.8, inner_stroke_color="#FF007F",
    glow_blur=16.0, glow_color="#FF007F",
    active_gradient=("#FF007F", "#FFAA00"),
    accent="&H0000AEAA", active="underline",
    outline="&H001A1024", outline_width=1.3, shadow=3.0,
    headline="plain")

add(key="paper",
    label="Paper II · Polished Editorial Pill",
    description="Cream morphing solid pill behind the line, dark editorial serif text in Merriweather, and spring glider motion.",
    font="Merriweather", headline_font="Merriweather",
    zone="lower", lower_margin=0.18, size=0.98, max_words=3,
    caption_box="pill", box_radius=0.44, box_pad_x=0.38,
    kinetic_mode="glider", spring_tension=200.0, spring_friction=18.0,
    shadow_blur=14.0, shadow_y=5.0, shadow_color="rgba(0, 0, 0, 0.35)",
    fill="&H00F7ECE7", fill_text=DARK_PAPER, fill_opacity=0.96,
    accent="&H002ACBC7", active="accent",
    headline="serif", headline_color=DARK_PAPER)

add(key="evo",
    label="Evo · Frosted Glass Gradient Pill & Cyan Pop",
    description="Frosted glass translucent rounded pill with Montserrat typography, dynamic cyan glow pop, and elastic glider.",
    font="Montserrat", headline_font="Montserrat",
    uppercase=True, zone="lower", lower_margin=0.17, size=1.02, max_words=3,
    caption_box="pill", box_radius=0.48, box_pad_x=0.46,
    kinetic_mode="glider", spring_tension=200.0, spring_friction=18.0,
    glow_blur=18.0, glow_color="#00FFFF",
    active_gradient=("#D0FFFF", "#00FFFF"),
    fill="&H221832", fill_opacity=0.34, fill_text=WHITE,
    accent="&H0000FFFF", upcoming="&H00A9A9A9",
    outline="&H00161420", outline_width=1.2, shadow=1.5,
    headline="plain")

add(key="linen",
    label="Linen · Editorial Serif Hook & Subtitles",
    description="Editorial serif dialogue in Merriweather, editorial hairline rule, serif hook headline, and airy wave motion.",
    font="Merriweather", headline_font="Merriweather",
    zone="lower", lower_margin=0.21, size=0.98, letter_spacing=0.5,
    kinetic_mode="wave", spring_tension=210.0, spring_friction=19.0,
    outer_stroke_width=0.8, outer_stroke_color="#1E1C1A",
    shadow_blur=5.0, shadow_y=2.0, shadow_color="rgba(0, 0, 0, 0.50)",
    primary=CREAM, accent="&H0000C4A8",
    headline="serif", headline_color=CREAM,
    outline_width=0.7, shadow=1.5,
    frame="rules", frame_color=CREAM)

add(key="focus",
    label="Focus · Inverted Dialogue Badge Boxes",
    description="Word-sized inverted badge boxes, top hook headline, accent spoken word with spring pop.",
    font="Montserrat", headline_font="Montserrat",
    uppercase=True, zone="lower", lower_margin=0.17, size=0.94,
    caption_box="per_word", active="box",
    kinetic_mode="pop", spring_tension=280.0, spring_friction=24.0,
    shadow_blur=8.0, shadow_y=4.0, shadow_color="rgba(0, 0, 0, 0.60)",
    accent="&H0000FFFF",
    headline="badge",
    outline_width=0.9, shadow=1.5)

add(key="stack",
    label="Stack · Brutalist Technical Box & Grid",
    description="Monospace in JetBrains Mono, brutalist grid frame, bracketed spoken words, and neon chartreuse gradient.",
    font="JetBrains Mono", headline_font="JetBrains Mono",
    uppercase=True, zone="lower", lower_margin=0.18, size=0.86,
    letter_spacing=0.6, active="bracket",
    kinetic_mode="pop", spring_tension=250.0, spring_friction=18.0,
    active_gradient=("#FAFF00", "#70FF00"),
    outer_stroke_width=1.6, outer_stroke_color="#000000",
    accent="&H0000FFFF", upcoming="&H00777777",
    headline="kicker", frame="grid", frame_color="&H0000FFFF",
    rail="CUTFLOW // MOTION GRAPHICS", rail_color="&H0000FFFF")

add(key="y2k",
    label="Y2K · Cyberpunk Scanlines",
    description="Cyber grid + scanline frame in JetBrains Mono, electric magenta glow pass, and wave motion.",
    font="JetBrains Mono", headline_font="JetBrains Mono",
    uppercase=True, zone="center", size=0.94,
    kinetic_mode="wave", spring_tension=240.0, spring_friction=16.0,
    glow_blur=20.0, glow_color="#FF007F",
    active_gradient=("#FF007F", "#FFAA00"),
    accent="&H000051FF", active="marker",
    fill="&H000051FF", fill_opacity=0.30,
    headline="kicker",
    frame="scanlines", frame_color="&H000051FF", frame_opacity=0.30,
    rail="Y2K // SIGNAL", rail_color="&H000051FF",
    outline=BLACK, outline_width=1.4, shadow=3.0)

add(key="lift",
    label="Lift · Curved Header Banner & Emerald Pop",
    description="Filled rounded header banner with Bebas Neue typography, emerald active gradient, and pop overshoot.",
    font="Bebas Neue", headline_font="Bebas Neue",
    uppercase=True, zone="lower", lower_margin=0.16, size=1.06,
    kinetic_mode="pop", spring_tension=260.0, spring_friction=16.0,
    active_gradient=("#B5FFEA", "#05FFD5"),
    outer_stroke_width=1.8, outer_stroke_color="#101812",
    accent="&H0005FFD5", active="underline",
    headline="banner", headline_color="&H00141610",
    outline="&H00101812", outline_width=1.15)

add(key="chalk",
    label="Chalk · Tutorial Sketch Highlighter",
    description="Marker highlight on the spoken word, hairline rules, soft serif Merriweather with sketch wave.",
    font="Merriweather", headline_font="Merriweather",
    zone="lower", lower_margin=0.20, size=0.90, letter_spacing=0.3,
    kinetic_mode="wave", spring_tension=220.0, spring_friction=18.0,
    shadow_blur=6.0, shadow_y=3.0, shadow_color="rgba(0, 0, 0, 0.40)",
    accent="&H0000D4FD", active="marker",
    fill="&H0000D4FD", fill_opacity=0.30,
    headline="kicker",
    frame="rules", frame_color="&H0000D4FD", frame_opacity=0.55,
    outline_width=0.9, shadow=1.5)

add(key="pulse",
    label="Pulse Viral (Karaoke)",
    description="Bold uppercase wave in Montserrat with crisp mint active gradient and grey upcoming words.",
    font="Montserrat", headline_font="Montserrat",
    uppercase=True, zone="lower", lower_margin=0.17, size=1.06,
    karaoke=True, active="accent",
    kinetic_mode="wave", spring_tension=220.0, spring_friction=18.0,
    outer_stroke_width=2.0, outer_stroke_color="#121410",
    active_gradient=("#C6FFED", "#66F4C6"),
    accent="&H0066F4C6",
    headline="none")

add(key="elevate",
    label="Elevate · Luxury Minimal",
    description="Letterspaced small caps, hairline rules, understated gold underline, and wave motion.",
    font="Montserrat", headline_font="Montserrat",
    uppercase=True, zone="lower", lower_margin=0.22, size=0.82,
    letter_spacing=2.2, active="underline",
    kinetic_mode="wave", spring_tension=200.0, spring_friction=20.0,
    outer_stroke_width=0.5, outer_stroke_color="#101010",
    primary="&H00F2F2F2", accent="&H00009C63", upcoming="&H00666666",
    headline="kicker", frame="rules", frame_color="&H00788C99",
    outline_width=0.5, shadow=1.0)

add(key="karaoke",
    label="Dynamic Karaoke Pill",
    description="Translucent pill behind the line, lime spoken word, warm shadow, and elastic glider.",
    font="Montserrat", headline_font="Montserrat",
    zone="lower", lower_margin=0.17, size=0.96,
    caption_box="pill", box_radius=0.48, box_pad_x=0.42,
    kinetic_mode="glider", spring_tension=210.0, spring_friction=18.0,
    fill="&H00131A1B", fill_opacity=0.42, fill_text=WHITE,
    karaoke=True, active="accent", accent="&H00D5FF5F",
    headline="none",
    outline="&H00181A14", shadow=2.5)

add(key="clean",
    label="Clean Subtitles",
    description="Minimal white dialogue, subtle outline, no karaoke motion.",
    font="Montserrat", headline_font="Montserrat",
    zone="lower", lower_margin=0.17, size=0.92,
    karaoke=False, active="none",
    kinetic_mode="none",
    accent="&H0066F4C6",
    headline="none",
    outline_width=0.85, shadow=2.0)


def get(key: str) -> CaptionSpec | None:
    return PRESETS.get(key)


CAPTION_STYLE_ORDER = list(PRESETS.keys())
