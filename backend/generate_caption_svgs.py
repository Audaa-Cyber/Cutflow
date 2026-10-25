from pathlib import Path

out_dir = Path("frontend/assets/captions")
out_dir.mkdir(parents=True, exist_ok=True)

styles_data = {
    "focus": {
        "title": "FOCUS",
        "sub": "Inverted Badges",
        "bg1": "#181a20", "bg2": "#0c0d10",
        "tag": "FLAGSHIP",
        "category": "flagship",
        "headline": "THE BIGGEST MISTAKE",
        "badge_bg": "#ffffff", "badge_text": "#000000",
        "active": "BADGE BOXES",
        "before": "you make with",
        "after": "in your videos",
        "accent": "#ffffff",
        "light": "#4a90e2",
    },
    "linen": {
        "title": "LINEN",
        "sub": "Editorial Serif",
        "bg1": "#201c18", "bg2": "#0e0c0a",
        "tag": "EDITORIAL",
        "category": "flagship",
        "headline": "The Subtle Truth",
        "font_family": "Georgia, serif",
        "active": "captivating rhythm",
        "before": "creating an",
        "after": "that viewers feel",
        "accent": "#f5d799",
        "light": "#ffaa40",
    },
    "evo": {
        "title": "EVO",
        "sub": "Frosted Neon Pill",
        "bg1": "#18142a", "bg2": "#0a0714",
        "tag": "CYBER GLASS",
        "category": "flagship",
        "headline": "FUTURE OF EDITING",
        "pill": True,
        "active": "CYAN FLOW",
        "before": "harness the",
        "after": "effortlessly now",
        "accent": "#00f7ff",
        "light": "#7b2cbf",
    },
    "lift": {
        "title": "LIFT",
        "sub": "Emerald Header",
        "bg1": "#10221c", "bg2": "#07110d",
        "tag": "FLAGSHIP",
        "category": "flagship",
        "banner": "KEY STRATEGY",
        "headline": "HOW TO SCALE 10X",
        "active": "HYPER SPEED",
        "before": "unlocking",
        "after": "for your brand",
        "accent": "#38ef7d",
        "light": "#11998e",
    },
    "stack": {
        "title": "STACK",
        "sub": "Brutalist Tech Grid",
        "bg1": "#131920", "bg2": "#090c10",
        "tag": "BRUTALIST",
        "category": "flagship",
        "side_text": "SYS // 04.9",
        "headline": "CRITICAL INSIGHT",
        "active": "[MASSIVE LEAP]",
        "before": "this is the",
        "after": "you were seeking",
        "accent": "#00f0ff",
        "light": "#0072ff",
    },
    "align": {
        "title": "ALIGN",
        "sub": "Letterbox Dialogue",
        "bg1": "#181818", "bg2": "#0c0c0c",
        "tag": "MINIMAL",
        "category": "flagship",
        "headline": "A SIMPLE TRUTH",
        "active": "CLEAN DIALOGUE",
        "before": "mastering",
        "after": "with clarity",
        "accent": "#ffffff",
        "light": "#666666",
        "letterbox": True,
    },
    "prime": {
        "title": "PRIME",
        "sub": "Viral Active Pop",
        "bg1": "#221e10", "bg2": "#0f0d06",
        "tag": "VIRAL",
        "category": "viral",
        "headline": "DO NOT MISS THIS",
        "active": "VIRAL POP",
        "before": "everyone needs",
        "after": "on their feed",
        "accent": "#ffea00",
        "light": "#ff6b6b",
    },
    "impact": {
        "title": "IMPACT II",
        "sub": "Bold Punch",
        "bg1": "#241812", "bg2": "#100906",
        "tag": "VIRAL",
        "category": "viral",
        "headline": "RULE NUMBER ONE",
        "active": "NEVER QUIT",
        "before": "you should",
        "after": "no matter what",
        "accent": "#ffea00",
        "light": "#ee5253",
    },
    "paper": {
        "title": "PAPER II",
        "sub": "Polished Pill",
        "bg1": "#1c1e22", "bg2": "#0d0e10",
        "tag": "PREMIUM",
        "category": "luxury",
        "headline": "CHAPTER TWO",
        "pill": True,
        "active": "SMART WORK",
        "before": "it comes down to",
        "after": "every single day",
        "accent": "#ff9f43",
        "light": "#f368e0",
    },
    "elevate": {
        "title": "ELEVATE",
        "sub": "Luxury Minimal",
        "bg1": "#191919", "bg2": "#0d0d0d",
        "tag": "LUXURY",
        "category": "luxury",
        "headline": "Pure Perfection",
        "active": "Timeless Design",
        "before": "elevate with",
        "after": "in every frame",
        "accent": "#e5c07b",
        "light": "#98c379",
    },
    "pop": {
        "title": "POP",
        "sub": "Neon Kinetic",
        "bg1": "#201430", "bg2": "#0e0818",
        "tag": "KINETIC",
        "category": "viral",
        "headline": "CRAZY ENERGY",
        "active": "NEON BOUNCE",
        "before": "feel that",
        "after": "right here",
        "accent": "#e056fd",
        "light": "#be2edd",
    },
    "y2k": {
        "title": "Y2K",
        "sub": "Cyberpunk Glow",
        "bg1": "#221124", "bg2": "#0f0612",
        "tag": "RETRO",
        "category": "viral",
        "headline": "MATRIX LEVEL",
        "active": "CYBER GLOW",
        "before": "stepping into",
        "after": "new dimension",
        "accent": "#ff38cd",
        "light": "#00d2d3",
    },
    "chalk": {
        "title": "CHALK",
        "sub": "Highlighter",
        "bg1": "#122026", "bg2": "#080e12",
        "tag": "TUTORIAL",
        "category": "viral",
        "headline": "HOW TO BUILD THIS",
        "active": "KEY SECRET",
        "before": "here is the",
        "after": "you need today",
        "accent": "#00d2d3",
        "light": "#54a0ff",
    },
    "clean": {
        "title": "CLEAN",
        "sub": "Standard Subtitle",
        "bg1": "#15171a", "bg2": "#090a0c",
        "tag": "MINIMAL",
        "category": "minimal",
        "headline": "Clear Delivery",
        "active": "Natural Voice",
        "before": "listen to the",
        "after": "speaking clearly",
        "accent": "#54a0ff",
        "light": "#5f27cd",
    },
    "pulse": {
        "title": "PULSE",
        "sub": "Karaoke Mint",
        "bg1": "#12221e", "bg2": "#08100e",
        "tag": "KARAOKE",
        "category": "viral",
        "headline": "RHYTHMIC CADENCE",
        "active": "PULSE FLOW",
        "before": "sync to the",
        "after": "every second",
        "accent": "#1dd1a1",
        "light": "#10ac84",
    },
    "glow": {
        "title": "GLOW",
        "sub": "Neon Diffusion",
        "bg1": "#0f2224", "bg2": "#061011",
        "tag": "GLOW",
        "category": "viral",
        "headline": "RADIANT BEAMS",
        "active": "NEON LIGHT",
        "before": "illuminate the",
        "after": "all around us",
        "accent": "#10ac84",
        "light": "#01a3a4",
    },
    "hormozi": {
        "title": "HORMOZI",
        "sub": "Bold Gold Pop",
        "bg1": "#221c10", "bg2": "#0f0c05",
        "tag": "VIRAL",
        "category": "viral",
        "headline": "MILLION DOLLAR HABIT",
        "active": "MONEY PRINT",
        "before": "this literally will",
        "after": "every day",
        "accent": "#ff9f1a",
        "light": "#ee5253",
    },
    "karaoke": {
        "title": "KARAOKE",
        "sub": "Cutflow Lime",
        "bg1": "#182210", "bg2": "#0a1106",
        "tag": "KARAOKE",
        "category": "flagship",
        "headline": "PERFECT TIMING",
        "pill": True,
        "active": "LIME PILL",
        "before": "highlighting with",
        "after": "word by word",
        "accent": "#d5ff5f",
        "light": "#10ac84",
    },
}

for key, d in styles_data.items():
    font = d.get("font_family", "system-ui, -apple-system, sans-serif")
    accent = d["accent"]
    light = d.get("light", accent)
    headline = d.get("headline", "")

    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 640" width="360" height="640">',
        '  <defs>',
        f'    <linearGradient id="bg_{key}" x1="0%" y1="0%" x2="100%" y2="100%">',
        f'      <stop offset="0%" stop-color="{d["bg1"]}"/>',
        f'      <stop offset="100%" stop-color="{d["bg2"]}"/>',
        '    </linearGradient>',
        f'    <radialGradient id="light_{key}" cx="50%" cy="35%" r="60%">',
        f'      <stop offset="0%" stop-color="{light}" stop-opacity="0.22"/>',
        f'      <stop offset="70%" stop-color="{d["bg2"]}" stop-opacity="0"/>',
        '    </radialGradient>',
        '    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">',
        '      <feGaussianBlur stdDeviation="6" result="blur"/>',
        '      <feComposite in="SourceGraphic" in2="blur" operator="over"/>',
        '    </filter>',
        '  </defs>',
        f'  <rect width="360" height="640" fill="url(#bg_{key})"/>',
        f'  <rect width="360" height="640" fill="url(#light_{key})"/>',
        '  <!-- Simulated Video Speaker Silhouette -->',
        '  <g fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.06)" stroke-width="1.5">',
        '    <circle cx="180" cy="250" r="54"/>',
        '    <path d="M90 380 Q180 320 270 380 L270 410 L90 410 Z"/>',
        '  </g>',
        '  <!-- Subtle Soundwaves Background -->',
        '  <g fill="rgba(255,255,255,0.07)">',
        '    <rect x="36" y="340" width="3" height="18" rx="1.5"/>',
        '    <rect x="44" y="332" width="3" height="34" rx="1.5"/>',
        '    <rect x="52" y="324" width="3" height="50" rx="1.5"/>',
        '    <rect x="60" y="336" width="3" height="26" rx="1.5"/>',
        '    <rect x="300" y="336" width="3" height="26" rx="1.5"/>',
        '    <rect x="308" y="324" width="3" height="50" rx="1.5"/>',
        '    <rect x="316" y="332" width="3" height="34" rx="1.5"/>',
        '    <rect x="324" y="340" width="3" height="18" rx="1.5"/>',
        '  </g>',
        '  <!-- Top Status Pill -->',
        '  <rect x="20" y="22" width="86" height="24" rx="12" fill="rgba(0,0,0,0.5)" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>',
        f'  <text x="63" y="38" fill="{accent}" font-family="system-ui, sans-serif" font-size="9" font-weight="800" letter-spacing="1" text-anchor="middle">{d["tag"]}</text>',
        '  <circle cx="334" cy="34" r="3" fill="rgba(255,255,255,0.45)"/>',
        '  <circle cx="323" cy="34" r="3" fill="rgba(255,255,255,0.45)"/>',
        '  <circle cx="312" cy="34" r="3" fill="rgba(255,255,255,0.45)"/>',
    ]

    # Upper Third Hook Headline (Zone 1)
    if d.get("banner"):
        svg_parts.extend([
            '  <g transform="translate(180, 115)">',
            f'    <rect x="-80" y="-15" width="160" height="30" rx="15" fill="{accent}"/>',
            f'    <text x="0" y="5" fill="#071a13" font-family="{font}" font-size="11" font-weight="900" letter-spacing="1.5" text-anchor="middle">{d["banner"]}</text>',
            '  </g>',
            f'  <text x="180" y="166" fill="#ffffff" font-family="{font}" font-size="15" font-weight="900" letter-spacing="0.5" text-anchor="middle">{headline}</text>',
        ])
    elif d.get("badge_bg"):
        svg_parts.extend([
            '  <g transform="translate(180, 125)">',
            '    <rect x="-105" y="-17" width="210" height="34" rx="8" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>',
            f'    <text x="0" y="5" fill="#ffffff" font-family="{font}" font-size="12" font-weight="800" letter-spacing="1.2" text-anchor="middle">{headline}</text>',
            '  </g>',
        ])
    elif headline:
        svg_parts.append(
            f'  <text x="180" y="135" fill="#ffffff" font-family="{font}" font-size="15" font-weight="800" letter-spacing="0.8" text-anchor="middle" opacity="0.95">{headline}</text>'
        )

    if d.get("side_text"):
        svg_parts.append(
            f'  <g transform="translate(24, 300) rotate(-90)"><text x="0" y="0" fill="{accent}" font-family="monospace" font-size="9" font-weight="800" letter-spacing="2" opacity="0.75">{d["side_text"]}</text></g>'
        )

    if d.get("letterbox"):
        svg_parts.extend([
            '  <rect x="24" y="390" width="312" height="136" rx="6" fill="rgba(0,0,0,0.5)" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>',
        ])

    # Lower Third Dialogue Subtitles (Zone 3)
    svg_parts.extend([
        '  <g transform="translate(180, 440)">',
        f'    <text x="0" y="-30" fill="rgba(255,255,255,0.65)" font-family="{font}" font-size="14" font-weight="600" text-anchor="middle">{d["before"]}</text>',
    ])

    if d.get("badge_bg"):
        svg_parts.extend([
            f'    <rect x="-85" y="-12" width="170" height="38" rx="8" fill="{d["badge_bg"]}"/>',
            f'    <text x="0" y="13" fill="{d["badge_text"]}" font-family="{font}" font-size="17" font-weight="900" letter-spacing="0.5" text-anchor="middle">{d["active"]}</text>',
        ])
    elif d.get("pill"):
        svg_parts.extend([
            f'    <rect x="-85" y="-12" width="170" height="38" rx="19" fill="rgba(255,255,255,0.15)" stroke="{accent}" stroke-width="2"/>',
            f'    <text x="0" y="13" fill="{accent}" font-family="{font}" font-size="16" font-weight="800" letter-spacing="0.8" text-anchor="middle">{d["active"]}</text>',
        ])
    elif d.get("side_text"):
        svg_parts.extend([
            f'    <rect x="-85" y="-12" width="170" height="38" rx="4" fill="#000000" stroke="{accent}" stroke-width="2"/>',
            f'    <text x="0" y="13" fill="{accent}" font-family="monospace" font-size="15" font-weight="800" letter-spacing="1" text-anchor="middle">{d["active"]}</text>',
        ])
    else:
        svg_parts.append(
            f'    <text x="0" y="15" fill="{accent}" font-family="{font}" font-size="20" font-weight="900" letter-spacing="0.5" text-anchor="middle" filter="url(#glow)">{d["active"]}</text>'
        )

    svg_parts.extend([
        f'    <text x="0" y="52" fill="rgba(255,255,255,0.5)" font-family="{font}" font-size="13" font-weight="600" text-anchor="middle">{d["after"]}</text>',
        '  </g>',
        '  <!-- Bottom Style Name Bar -->',
        '  <rect x="18" y="582" width="324" height="40" rx="10" fill="rgba(0,0,0,0.7)" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>',
        f'  <text x="34" y="607" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="800">{d["title"]}</text>',
        f'  <text x="326" y="607" fill="{accent}" font-family="system-ui, sans-serif" font-size="10" font-weight="600" text-anchor="end">{d["sub"]}</text>',
        '</svg>',
    ])

    (out_dir / f"{key}.svg").write_text("\n".join(svg_parts), encoding="utf-8")

print(f"Generated {len(styles_data)} ultra-clean SVG preview cards.")
