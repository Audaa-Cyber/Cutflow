"""Generate default vector sticker SVGs and synthesized 16-bit PCM WAV SFX assets.

Produces crisp, self-contained assets for:
1. 12 Creator Vector Stickers (fire, rocket, money, brain, warning, lightning, trophy, chart_up, target, skull, heart, crown)
2. 4 Synced Sound Effects (pop.wav, click.wav, whoosh.wav, punch.wav)
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
import wave

STICKERS_SVG = {
    "fire": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="fireGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#FF1A00"/>
      <stop offset="55%" stop-color="#FF7700"/>
      <stop offset="100%" stop-color="#FFDD00"/>
    </linearGradient>
    <linearGradient id="fireCore" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#FFCC00"/>
      <stop offset="100%" stop-color="#FFFFFF"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>
  <g filter="url(#shadow)">
    <!-- White Sticker Die-cut Border -->
    <path d="M64 6 C48 24 30 46 30 74 C30 96 45 116 64 116 C83 116 98 96 98 74 C98 52 82 30 76 22 C74 34 68 42 60 46 C66 32 68 18 64 6 Z"
          fill="#FFFFFF" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>
    <!-- Outer Flame Body -->
    <path d="M64 6 C48 24 30 46 30 74 C30 96 45 116 64 116 C83 116 98 96 98 74 C98 52 82 30 76 22 C74 34 68 42 60 46 C66 32 68 18 64 6 Z"
          fill="url(#fireGrad)"/>
    <!-- Inner Core -->
    <path d="M64 48 C54 60 44 72 44 88 C44 102 53 112 64 112 C75 112 84 102 84 88 C84 76 74 64 70 58 C68 64 64 68 60 70 C63 62 65 54 64 48 Z"
          fill="url(#fireCore)" opacity="0.95"/>
  </g>
</svg>""",

    "rocket": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="rocketBody" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="100%" stop-color="#DCE3EE"/>
    </linearGradient>
    <linearGradient id="rocketPlume" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFDD00"/>
      <stop offset="100%" stop-color="#FF2200"/>
    </linearGradient>
  </defs>
  <!-- Flame Plume -->
  <path d="M42 86 L24 104 C20 108 26 114 30 110 L48 92 Z" fill="url(#rocketPlume)" stroke="#FFFFFF" stroke-width="4"/>
  <!-- Fins -->
  <path d="M52 64 L26 84 C22 87 26 94 32 94 L58 84 Z" fill="#FF2A4B" stroke="#FFFFFF" stroke-width="4"/>
  <path d="M64 52 L84 26 C87 22 94 26 94 32 L84 58 Z" fill="#FF2A4B" stroke="#FFFFFF" stroke-width="4"/>
  <!-- Main Fuselage -->
  <path d="M96 32 C78 20 54 34 44 56 C40 64 38 74 38 84 L44 90 C54 90 64 88 72 84 C94 74 108 50 96 32 Z"
        fill="url(#rocketBody)" stroke="#FFFFFF" stroke-width="6" stroke-linejoin="round"/>
  <!-- Porthole Window -->
  <circle cx="70" cy="58" r="10" fill="#00D2FF" stroke="#FFFFFF" stroke-width="3"/>
  <circle cx="68" cy="56" r="3" fill="#FFFFFF"/>
  <!-- Tip Cone -->
  <path d="M96 32 C91 27 82 23 76 22 C84 32 90 40 96 32 Z" fill="#FF2A4B"/>
</svg>""",

    "money": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="billGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00E676"/>
      <stop offset="100%" stop-color="#00A344"/>
    </linearGradient>
  </defs>
  <!-- Flying Money Wings -->
  <path d="M22 46 C32 28 50 36 46 54 C34 56 22 56 22 46 Z" fill="#E8F5E9" stroke="#FFFFFF" stroke-width="4"/>
  <path d="M106 46 C96 28 78 36 82 54 C94 56 106 56 106 46 Z" fill="#E8F5E9" stroke="#FFFFFF" stroke-width="4"/>
  <!-- Dollar Bill Stack -->
  <rect x="28" y="44" width="72" height="46" rx="8" transform="rotate(-6 64 67)"
        fill="#007E33" stroke="#FFFFFF" stroke-width="5"/>
  <rect x="28" y="40" width="72" height="46" rx="8"
        fill="url(#billGrad)" stroke="#FFFFFF" stroke-width="6"/>
  <!-- Border Inset -->
  <rect x="34" y="46" width="60" height="34" rx="4" fill="none" stroke="#A7FFEB" stroke-width="2" stroke-dasharray="4 2"/>
  <!-- Center Seal -->
  <circle cx="64" cy="63" r="13" fill="#00C853" stroke="#FFFFFF" stroke-width="2"/>
  <text x="64" y="70" font-family="Arial, sans-serif" font-weight="900" font-size="20" fill="#FFFFFF" text-anchor="middle">$</text>
</svg>""",

    "brain": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="brainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF4081"/>
      <stop offset="100%" stop-color="#7C4DFF"/>
    </linearGradient>
  </defs>
  <!-- Die Cut Outer Outline -->
  <g stroke="#FFFFFF" stroke-width="6" stroke-linejoin="round">
    <path d="M64 28 C56 20 42 22 36 32 C28 32 22 42 24 52 C18 58 18 70 24 76 C22 86 30 96 40 96 C46 102 58 102 64 96 C70 102 82 102 88 96 C98 96 106 86 104 76 C110 70 110 58 104 52 C106 42 100 32 92 32 C86 22 72 20 64 28 Z"
          fill="url(#brainGrad)"/>
  </g>
  <!-- Brain Gyri & Sulci -->
  <path d="M64 32 L64 92" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" opacity="0.6"/>
  <path d="M42 44 C50 44 54 50 48 58 C42 66 52 74 58 72" fill="none" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M86 44 C78 44 74 50 80 58 C86 66 76 74 70 72" fill="none" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="34" cy="62" r="3" fill="#FFFFFF"/>
  <circle cx="94" cy="62" r="3" fill="#FFFFFF"/>
</svg>""",

    "warning": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="warnGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFE600"/>
      <stop offset="100%" stop-color="#FF9100"/>
    </linearGradient>
  </defs>
  <!-- Warning Triangle Shield -->
  <polygon points="64,16 116,104 12,104"
           fill="url(#warnGrad)" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>
  <!-- Inner Exclamation Mark -->
  <path d="M64 42 L64 74" stroke="#101010" stroke-width="9" stroke-linecap="round"/>
  <circle cx="64" cy="88" r="5.5" fill="#101010"/>
</svg>""",

    "lightning": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="boltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFF500"/>
      <stop offset="100%" stop-color="#FF8800"/>
    </linearGradient>
  </defs>
  <!-- Lightning Bolt -->
  <polygon points="72,12 30,68 62,68 46,116 98,54 68,54"
           fill="url(#boltGrad)" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>
</svg>""",

    "trophy": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFF275"/>
      <stop offset="50%" stop-color="#FFC107"/>
      <stop offset="100%" stop-color="#FFA000"/>
    </linearGradient>
  </defs>
  <!-- Handles -->
  <path d="M34 32 C20 32 20 60 38 64" fill="none" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
  <path d="M94 32 C108 32 108 60 90 64" fill="none" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
  <path d="M34 32 C22 32 22 58 38 62" fill="none" stroke="#FFB300" stroke-width="5" stroke-linecap="round"/>
  <path d="M94 32 C106 32 106 58 90 62" fill="none" stroke="#FFB300" stroke-width="5" stroke-linecap="round"/>
  <!-- Cup Body -->
  <path d="M34 24 L94 24 C94 56 78 72 64 72 C50 72 34 56 34 24 Z"
        fill="url(#goldGrad)" stroke="#FFFFFF" stroke-width="6"/>
  <!-- Stem & Base -->
  <path d="M58 72 L70 72 L68 92 L60 92 Z" fill="#FFA000" stroke="#FFFFFF" stroke-width="4"/>
  <rect x="42" y="92" width="44" height="18" rx="4" fill="#3E2723" stroke="#FFFFFF" stroke-width="5"/>
  <!-- Star Emblem -->
  <polygon points="64,36 67,44 75,44 69,49 71,57 64,52 57,57 59,49 53,44 61,44" fill="#FFFFFF"/>
</svg>""",

    "chart_up": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="trendGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00E676"/>
      <stop offset="100%" stop-color="#00B0FF"/>
    </linearGradient>
  </defs>
  <!-- Background Badge -->
  <rect x="14" y="14" width="100" height="100" rx="22" fill="#111B24" stroke="#FFFFFF" stroke-width="6"/>
  <!-- Ascending Green Bars -->
  <rect x="28" y="74" width="12" height="26" rx="3" fill="#00E676" opacity="0.6"/>
  <rect x="46" y="60" width="12" height="40" rx="3" fill="#00E676" opacity="0.8"/>
  <rect x="64" y="44" width="12" height="56" rx="3" fill="#00E676"/>
  <rect x="82" y="30" width="12" height="70" rx="3" fill="#00E676"/>
  <!-- Trend Arrow -->
  <polyline points="28,68 48,52 68,40 92,24" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="96,22 84,22 96,34" fill="#FFFFFF"/>
</svg>""",

    "target": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <!-- Outer Red Ring -->
  <circle cx="64" cy="64" r="52" fill="#FF1744" stroke="#FFFFFF" stroke-width="7"/>
  <!-- Middle White Ring -->
  <circle cx="64" cy="64" r="38" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="2"/>
  <!-- Inner Red Ring -->
  <circle cx="64" cy="64" r="24" fill="#FF1744"/>
  <!-- Bullseye Center -->
  <circle cx="64" cy="64" r="10" fill="#FFD600" stroke="#FFFFFF" stroke-width="3"/>
</svg>""",

    "skull": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="skullGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="100%" stop-color="#CFD8DC"/>
    </linearGradient>
  </defs>
  <!-- Crossbones -->
  <path d="M26 26 L102 102 M102 26 L26 102" stroke="#FFFFFF" stroke-width="14" stroke-linecap="round"/>
  <path d="M26 26 L102 102 M102 26 L26 102" stroke="#B0BEC5" stroke-width="8" stroke-linecap="round"/>
  <!-- Skull Cranium -->
  <path d="M38 60 C38 38 48 24 64 24 C80 24 90 38 90 60 C90 70 84 76 80 80 L80 94 L48 94 L48 80 C44 76 38 70 38 60 Z"
        fill="url(#skullGrad)" stroke="#FFFFFF" stroke-width="6" stroke-linejoin="round"/>
  <!-- Eye Sockets & Nose -->
  <circle cx="52" cy="56" r="9" fill="#263238"/>
  <circle cx="76" cy="56" r="9" fill="#263238"/>
  <polygon points="64,68 60,76 68,76" fill="#263238"/>
  <!-- Teeth -->
  <path d="M56 86 L56 94 M64 86 L64 94 M72 86 L72 94" stroke="#263238" stroke-width="3" stroke-linecap="round"/>
</svg>""",

    "heart": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="heartGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF1744"/>
      <stop offset="100%" stop-color="#D50000"/>
    </linearGradient>
  </defs>
  <!-- Die Cut Heart -->
  <path d="M64 112 C64 112 20 84 20 48 C20 28 36 16 52 16 C60 16 64 24 64 24 C64 24 68 16 76 16 C92 16 108 28 108 48 C108 84 64 112 64 112 Z"
        fill="url(#heartGrad)" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>
  <!-- Sheen Glint -->
  <ellipse cx="44" cy="36" rx="8" ry="14" transform="rotate(-30 44 36)" fill="#FFFFFF" opacity="0.45"/>
</svg>""",

    "crown": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="crownGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFE082"/>
      <stop offset="60%" stop-color="#FFD54F"/>
      <stop offset="100%" stop-color="#FFA000"/>
    </linearGradient>
  </defs>
  <!-- 3-Peak Crown -->
  <path d="M22 96 L28 42 L50 66 L64 30 L78 66 L100 42 L106 96 Z"
        fill="url(#crownGrad)" stroke="#FFFFFF" stroke-width="7" stroke-linejoin="round"/>
  <!-- Jewel Balls -->
  <circle cx="28" cy="40" r="6" fill="#FF1744" stroke="#FFFFFF" stroke-width="2"/>
  <circle cx="64" cy="28" r="7" fill="#00E5FF" stroke="#FFFFFF" stroke-width="2"/>
  <circle cx="100" cy="40" r="6" fill="#76FF03" stroke="#FFFFFF" stroke-width="2"/>
  <!-- Base Band with Gem Insets -->
  <rect x="22" y="86" width="84" height="12" rx="3" fill="#FF8F00"/>
  <circle cx="44" cy="92" r="3" fill="#FFFFFF"/>
  <circle cx="64" cy="92" r="3" fill="#FFFFFF"/>
  <circle cx="84" cy="92" r="3" fill="#FFFFFF"/>
</svg>""",
}


def synthesize_wav(duration_s: float, sample_rate: int, generator_func) -> bytes:
    """Generate uncompressed 16-bit mono PCM WAV bytes."""
    total_samples = int(duration_s * sample_rate)
    raw_samples = []

    for i in range(total_samples):
        t = i / sample_rate
        sample_float = generator_func(t, duration_s)
        sample_clamped = max(-1.0, min(1.0, sample_float))
        sample_int = int(sample_clamped * 32767.0)
        raw_samples.append(struct.pack("<h", sample_int))

    payload = b"".join(raw_samples)

    # Build standard 44-byte RIFF WAV header
    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", 36 + len(payload)))
    header.extend(b"WAVE")
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", 16))         # Subchunk1Size (16 for PCM)
    header.extend(struct.pack("<H", 1))          # AudioFormat (1 = PCM)
    header.extend(struct.pack("<H", 1))          # NumChannels (1 = Mono)
    header.extend(struct.pack("<I", sample_rate))# SampleRate
    header.extend(struct.pack("<I", sample_rate * 2)) # ByteRate (SampleRate * 1 channel * 2 bytes)
    header.extend(struct.pack("<H", 2))          # BlockAlign (1 * 2)
    header.extend(struct.pack("<H", 16))         # BitsPerSample
    header.extend(b"data")
    header.extend(struct.pack("<I", len(payload)))

    return bytes(header + payload)


def pop_sound(t: float, dur: float) -> float:
    """Crisp organic bubble pop sound (downward pitch envelope 750Hz -> 280Hz with fast decay)."""
    # Pitch envelope: sweeps from 780Hz down to 260Hz in 80ms
    freq = 260.0 + 520.0 * math.exp(-t * 45.0)
    phase = 2.0 * math.pi * freq * t
    amp = math.exp(-t * 38.0)
    return math.sin(phase) * amp * 0.85


def click_sound(t: float, dur: float) -> float:
    """Mechanical snappy UI click sound (1800Hz damped pulse with high-frequency click)."""
    if t > 0.045:
        return 0.0
    freq = 1900.0 * math.exp(-t * 90.0)
    phase = 2.0 * math.pi * freq * t
    amp = math.exp(-t * 110.0)
    return math.sin(phase) * amp * 0.75


def whoosh_sound(t: float, dur: float) -> float:
    """Aerodynamic whip-pan whoosh sound (bandpass noise sweep centered at 450Hz)."""
    # Sine frequency modulation simulation for air sweep
    freq = 180.0 + 580.0 * math.sin(math.pi * (t / dur))
    # Smooth bell envelope
    amp = math.sin(math.pi * (t / dur)) ** 2
    # Combined multi-tone harmonic layer for rush effect
    sig = math.sin(2.0 * math.pi * freq * t) * 0.6 + math.sin(2.0 * math.pi * freq * 1.5 * t) * 0.3
    return sig * amp * 0.70


def punch_sound(t: float, dur: float) -> float:
    """Punchy low-end impact tap (120Hz thud + 60Hz sub with rapid decay)."""
    freq = 60.0 + 140.0 * math.exp(-t * 28.0)
    phase = 2.0 * math.pi * freq * t
    amp = math.exp(-t * 22.0)
    return math.sin(phase) * amp * 0.90


def main():
    root = Path(__file__).resolve().parents[2]
    backend_stickers = root / "backend" / "assets" / "stickers"
    frontend_stickers = root / "frontend" / "assets" / "stickers"
    backend_sfx = root / "backend" / "assets" / "sfx"
    frontend_sfx = root / "frontend" / "assets" / "sfx"

    for d in (backend_stickers, frontend_stickers, backend_sfx, frontend_sfx):
        d.mkdir(parents=True, exist_ok=True)

    # Write SVGs
    for name, content in STICKERS_SVG.items():
        b_path = backend_stickers / f"{name}.svg"
        f_path = frontend_stickers / f"{name}.svg"
        b_path.write_text(content.strip(), encoding="utf-8")
        f_path.write_text(content.strip(), encoding="utf-8")
        print(f"[Assets] Wrote sticker: {name}.svg")

    # Generate WAVs
    sfx_defs = [
        ("pop.wav", 0.12, pop_sound),
        ("click.wav", 0.05, click_sound),
        ("whoosh.wav", 0.28, whoosh_sound),
        ("punch.wav", 0.18, punch_sound),
    ]

    for fname, duration, gen in sfx_defs:
        wav_data = synthesize_wav(duration, 44100, gen)
        (backend_sfx / fname).write_bytes(wav_data)
        (frontend_sfx / fname).write_bytes(wav_data)
        print(f"[Assets] Synthesized SFX: {fname} ({len(wav_data)} bytes)")


if __name__ == "__main__":
    main()

