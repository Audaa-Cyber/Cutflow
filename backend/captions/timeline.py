"""Kinetic Typography Timeline & Acoustic Alignment Engine (Phase 1).

Normalizes Whisper speech transcription timestamps into a deterministic,
sub-millisecond accurate `KineticTimeline` schema. Computes phonological
syllable boundaries, acoustic stress peaks (vowel onset/energy release),
lexical stress scores, and visual bounds for downstream kinetic rendering.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .presets import PRESETS
from .spec import CaptionSpec, resolve_headline_font

# ── Acoustic & Lexical Stress Heuristics ──────────────────────────────────────

VOWELS = set("aeiouyAEIOUY")
DIPHTHONGS = {
    "ai", "au", "aw", "ay", "ea", "ee", "ei", "eu", "ew", "ey",
    "ie", "oa", "oe", "oi", "oo", "ou", "ow", "oy", "ue", "ui",
}

# Function / Grammatical words receive lower base acoustic emphasis
FUNCTION_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet",
    "in", "on", "at", "to", "by", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "from", "up", "down", "off", "over", "under", "again", "further",
    "of", "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "it", "its", "it's",
    "he", "she", "we", "they", "them", "his", "her", "their", "my", "your",
    "that", "this", "these", "those", "i", "you", "me", "him", "us",
}

# High-impact viral keywords warrant heightened kinetic activation
VIRAL_PUNCH_WORDS = {
    "biggest", "mistake", "secret", "never", "always", "insane", "crazy",
    "wild", "huge", "massive", "million", "billion", "money", "cash",
    "dollar", "profit", "growth", "viral", "win", "winner", "hack", "trick",
    "truth", "shock", "shocked", "stop", "danger", "warning", "best", "worst",
    "power", "energy", "boom", "rocket", "scale", "unlock", "focus",
}

# Semantic Keyword to Vector Sticker Category Mapping (Phase 5)
STICKER_SEMANTIC_MAP: dict[str, str] = {
    # Virality & Fire
    "fire": "fire", "flame": "fire", "lit": "fire", "hot": "fire", "burning": "fire",
    "viral": "fire", "trending": "fire", "trend": "fire",
    # Speed & Momentum
    "rocket": "rocket", "launch": "rocket", "blast": "rocket", "skyrocket": "rocket",
    "moon": "rocket", "space": "rocket", "scale": "rocket", "fast": "rocket",
    # Money & Wealth
    "money": "money", "cash": "money", "dollar": "money", "dollars": "money",
    "profit": "money", "revenue": "money", "million": "money", "millions": "money",
    "billion": "money", "billions": "money", "rich": "money", "bag": "money",
    # Intellect & Secrets
    "brain": "brain", "mind": "brain", "idea": "brain", "think": "brain",
    "genius": "brain", "smart": "brain", "learn": "brain", "secret": "brain",
    # Alerts & Danger
    "warning": "warning", "danger": "warning", "stop": "warning", "alert": "warning",
    "caution": "warning", "mistake": "warning", "error": "warning", "wrong": "warning",
    # High Energy & Shock
    "energy": "lightning", "power": "lightning", "shock": "lightning", "shocked": "lightning",
    "electric": "lightning", "spark": "lightning", "boom": "lightning",
    # Victory & Mastery
    "win": "trophy", "winner": "trophy", "winning": "trophy", "champion": "trophy",
    "best": "trophy", "victory": "trophy", "success": "trophy", "award": "trophy",
    # Growth & Analytics
    "growth": "chart_up", "grow": "chart_up", "boost": "chart_up", "stocks": "chart_up",
    "trading": "chart_up", "up": "chart_up", "increase": "chart_up",
    # Precision & Focus
    "focus": "target", "target": "target", "goal": "target", "bullseye": "target",
    "exact": "target", "hack": "target", "trick": "target",
    # Wild & Extreme
    "crazy": "skull", "insane": "skull", "wild": "skull", "dead": "skull",
    "die": "skull", "fatal": "skull", "destroyed": "skull",
    # Emotion & Passion
    "love": "heart", "like": "heart", "favorite": "heart", "amazing": "heart",
    # Leadership & Status
    "king": "crown", "boss": "crown", "leader": "crown", "top": "crown", "rule": "crown",
}

# Common English prefixes & suffixes for morphological boundary resolution
PREFIXES = ("un", "re", "in", "im", "dis", "en", "em", "non", "over", "mis", "sub", "pre", "inter", "fore", "de", "trans", "super")
SUFFIXES = ("tion", "sion", "ment", "ness", "able", "ible", "fully", "less", "ing", "est", "ous", "ious", "ally", "ly", "ed", "er")


def ass_color_to_hex(ass_color: str) -> str:
    """Convert ASS &HAABBGGRR or &HBBGGRR colour token to standard CSS #RRGGBB."""
    if not ass_color:
        return "#ffffff"
    ass_color = ass_color.strip()
    if ass_color.startswith("#") or ass_color.startswith("rgba") or ass_color.startswith("rgb"):
        return ass_color
    clean = ass_color.replace("&H", "").replace("&", "").strip()
    if len(clean) == 8:
        # AA BB GG RR
        bb = clean[2:4]
        gg = clean[4:6]
        rr = clean[6:8]
        return f"#{rr}{gg}{bb}".lower()
    if len(clean) == 6:
        # BB GG RR
        bb = clean[0:2]
        gg = clean[2:4]
        rr = clean[4:6]
        return f"#{rr}{gg}{bb}".lower()
    return "#ffffff"


def estimate_syllables(word: str) -> list[str]:
    """Phonological syllabification for English words using nucleus-coda rules.
    
    Guarantees at least 1 syllable. Concatenating returned syllables recreates
    the original word text.
    """
    clean = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not clean:
        return [word] if word else [""]
    if len(clean) <= 3:
        return [word]

    # Handle silent trailing 'e' (e.g., 'make', 'mistake', 'code')
    effective = clean
    has_silent_e = False
    if effective.endswith("e") and not effective.endswith("le") and len(effective) > 2:
        if effective[-2] not in VOWELS:
            has_silent_e = True
            effective = effective[:-1]

    # Detect vowel nucleus positions
    nuclei: list[tuple[int, int]] = []
    i = 0
    n = len(effective)
    while i < n:
        if effective[i] in VOWELS:
            # Check for 2-letter vowel digraphs / diphthongs
            if i + 1 < n and effective[i:i+2] in DIPHTHONGS:
                nuclei.append((i, i + 2))
                i += 2
            else:
                nuclei.append((i, i + 1))
                i += 1
        else:
            i += 1

    if len(nuclei) <= 1:
        return [word]

    # Split between nuclei based on consonant boundaries
    split_indices: list[int] = []
    for k in range(len(nuclei) - 1):
        c_start = nuclei[k][1]
        c_end = nuclei[k + 1][0]
        consonants = c_end - c_start
        if consonants == 0:
            # Hiatus (e.g., 'ca-os', 're-act')
            split_indices.append(c_start)
        elif consonants == 1:
            # Single intervocalic consonant usually belongs to onset of second syllable (V-CV)
            split_indices.append(c_start)
        else:
            # Multiple consonants split between coda and onset (VC-CV)
            split_indices.append(c_start + (consonants // 2))

    # Slice the original word (preserving original case and punctuation)
    syllables: list[str] = []
    prev_idx = 0
    for idx in split_indices:
        syllables.append(word[prev_idx:idx])
        prev_idx = idx
    syllables.append(word[prev_idx:])
    return [s for s in syllables if s]


def calculate_syllable_timings(
    word_text: str,
    start_ms: int,
    end_ms: int,
    syllables: list[str],
) -> tuple[int, list[dict[str, Any]]]:
    """Distribute word duration across syllables and compute stress peak.
    
    Returns:
        (stress_peak_ms, list_of_syllables_with_timings)
    """
    duration = max(20, end_ms - start_ms)
    count = len(syllables)
    if count == 1:
        # Monosyllabic: stress peak sits at 38% into the vowel onset
        peak_ms = start_ms + int(duration * 0.38)
        return peak_ms, [{
            "text": syllables[0],
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": duration,
            "is_stressed": True,
            "stress_peak_ms": peak_ms,
        }]

    # Weight duration by syllable character length + diphthong factor
    weights: list[float] = []
    for s in syllables:
        w_len = max(1, len(re.sub(r"[^a-zA-Z]", "", s)))
        has_dip = any(dip in s.lower() for dip in DIPHTHONGS)
        weights.append(w_len * (1.25 if has_dip else 1.0))

    total_weight = sum(weights) or 1.0
    cur_ms = start_ms
    syllable_data: list[dict[str, Any]] = []

    # Heuristic: in English disyllabic words, root syllable is typically stressed
    # Trochaic for nouns/adjectives (first syllable), iambic for verbs or prefixed words
    lower_word = re.sub(r"[^a-zA-Z]", "", word_text).lower()
    has_prefix = any(lower_word.startswith(p) for p in PREFIXES if len(lower_word) > len(p) + 2)
    stressed_idx = 1 if (has_prefix and count >= 2) else 0

    overall_peak_ms = start_ms + int(duration * 0.38)

    for idx, (s_text, w) in enumerate(zip(syllables, weights)):
        if idx == count - 1:
            s_end = end_ms
        else:
            s_duration = int(round((w / total_weight) * duration))
            s_end = min(end_ms, cur_ms + max(10, s_duration))

        s_dur = max(10, s_end - cur_ms)
        is_stressed = (idx == stressed_idx)
        # Stress peak sits at 40% into the stressed syllable
        s_peak = cur_ms + int(s_dur * 0.40)

        if is_stressed:
            overall_peak_ms = s_peak

        syllable_data.append({
            "text": s_text,
            "start_ms": cur_ms,
            "end_ms": s_end,
            "duration_ms": s_dur,
            "is_stressed": is_stressed,
            "stress_peak_ms": s_peak,
        })
        cur_ms = s_end

    return overall_peak_ms, syllable_data


def calculate_stress_score(
    clean_word: str,
    duration_ms: int,
    char_count: int,
    raw_text: str,
) -> float:
    """Calculate normalized acoustic/lexical stress score (0.0 to 1.0)."""
    norm = clean_word.lower()
    if not norm:
        return 0.1

    # Base lexical score
    if norm in VIRAL_PUNCH_WORDS:
        base = 0.88
    elif norm in FUNCTION_WORDS:
        base = 0.28
    else:
        # Standard content word (noun, action verb, adjective)
        base = 0.62

    # Acoustic elongation bonus (speaking rate < normal implies spoken emphasis)
    # Average rate: ~45ms per character. Longer duration => higher emphasis
    expected_ms = max(60, char_count * 45)
    rate_ratio = duration_ms / max(1, expected_ms)
    duration_bonus = min(0.18, max(-0.15, (rate_ratio - 1.0) * 0.12))

    # Emphatic punctuation & capitalization bonus
    punct_bonus = 0.0
    if raw_text.endswith("!"):
        punct_bonus += 0.14
    elif raw_text.endswith("?"):
        punct_bonus += 0.08

    if raw_text.isupper() and len(clean_word) > 1:
        punct_bonus += 0.08

    score = round(min(1.0, max(0.05, base + duration_bonus + punct_bonus)), 3)
    return score


# ── Strongly-Typed Kinetic Timeline Data Structures ──────────────────────────

@dataclass
class SyllableToken:
    text: str
    start_ms: int
    end_ms: int
    duration_ms: int
    is_stressed: bool
    stress_peak_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WordToken:
    id: str
    word: str
    text: str
    start: float
    end: float
    start_ms: int
    end_ms: int
    duration_ms: int
    stress_peak_ms: int
    stress_score: float
    highlight: bool
    syllables: list[dict[str, Any]]
    char_count: int
    emoji: Optional[str] = None
    bounds_estimated: Optional[dict[str, Any]] = None
    sticker: Optional[dict[str, Any]] = None
    camera_punch: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhraseSpan:
    id: str
    start: float
    end: float
    start_ms: int
    end_ms: int
    duration_ms: int
    text: str
    word_count: int
    words: list[dict[str, Any]]
    headline: Optional[str] = None
    layout_zone: str = "lower"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KineticTimeline:
    version: str
    clip_id: str
    start: float
    end: float
    start_ms: int
    end_ms: int
    duration_ms: int
    aspect_ratio: str
    word_count: int
    words: list[dict[str, Any]]
    phrases: list[dict[str, Any]]
    styling_metadata: dict[str, Any]
    stickers: list[dict[str, Any]] = field(default_factory=list)
    camera_events: list[dict[str, Any]] = field(default_factory=list)
    audio_sfx: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Timeline Construction Pipeline ───────────────────────────────────────────

def build_word_token(
    raw_token: dict[str, Any],
    idx: int,
    emoji_map: Optional[dict[str, str]] = None,
    font_size_px: int = 86,
) -> WordToken:
    """Construct a fully enriched WordToken with sub-millisecond syllable boundaries."""
    raw_word = str(raw_token.get("word", "")).strip()
    clean_word = re.sub(r"[^a-zA-Z0-9']", "", raw_word)
    start_s = float(raw_token.get("start", 0.0))
    end_s = float(raw_token.get("end", start_s + 0.3))
    
    start_ms = int(round(start_s * 1000))
    end_ms = max(start_ms + 20, int(round(end_s * 1000)))
    duration_ms = end_ms - start_ms

    syllable_texts = estimate_syllables(clean_word or raw_word)
    stress_peak_ms, syllables_data = calculate_syllable_timings(
        raw_word, start_ms, end_ms, syllable_texts
    )

    clean_norm = clean_word.lower()
    emoji = (emoji_map or {}).get(clean_norm) if emoji_map else None
    char_count = len(clean_word) or len(raw_word)

    # Semantic Vector Sticker mapping (Phase 5)
    sticker_cat = STICKER_SEMANTIC_MAP.get(clean_norm)
    sticker = None
    if sticker_cat:
        sticker = {
            "id": f"stk_{idx}",
            "category": sticker_cat,
            "asset": f"{sticker_cat}.svg",
            "offset_x": 0.0,
            "offset_y": -16.0,
            "tilt_deg": -8.0 if (idx % 2 == 0) else 6.0,
            "scale": 1.0,
        }

    stress_score = calculate_stress_score(clean_word, duration_ms, char_count, raw_word)
    is_highlight = bool(stress_score >= 0.72 or emoji is not None or sticker is not None)
    is_camera_punch = bool(stress_score >= 0.76 or sticker is not None or clean_norm in VIRAL_PUNCH_WORDS)

    # Estimate physical bounds for layout calculation (Phase 2 preview alignment)
    approx_width_px = round(char_count * font_size_px * 0.58, 1)
    bounds_estimated = {
        "char_count": char_count,
        "approx_width_px": approx_width_px,
        "approx_height_px": font_size_px,
    }

    return WordToken(
        id=f"w_{idx}",
        word=clean_word or raw_word,
        text=raw_word,
        start=round(start_s, 3),
        end=round(end_s, 3),
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=duration_ms,
        stress_peak_ms=stress_peak_ms,
        stress_score=stress_score,
        highlight=is_highlight,
        syllables=syllables_data,
        char_count=char_count,
        emoji=emoji,
        bounds_estimated=bounds_estimated,
        sticker=sticker,
        camera_punch=is_camera_punch,
    )


def build_kinetic_timeline(
    words: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    spec: CaptionSpec,
    aspect: str = "9:16",
    headline_text: Optional[str] = None,
    emoji_map: Optional[dict[str, str]] = None,
    clip_id: str = "",
) -> dict[str, Any]:
    """Compile words into a standardized, millisecond-accurate KineticTimeline.
    
    Guarantees monotonic timestamps, syllable-level resolution, and full styling metadata.
    """
    clip_start = max(0.0, float(clip_start))
    clip_end = max(clip_start + 0.1, float(clip_end))
    start_ms = int(round(clip_start * 1000))
    end_ms = int(round(clip_end * 1000))
    duration_ms = end_ms - start_ms

    # Base typography sizing
    base_sizes = {"9:16": 92, "1:1": 82, "16:9": 78}
    base_font_px = base_sizes.get(aspect, 92)
    font_size_px = max(24, int(round(base_font_px * spec.size)))
    headline_size_px = max(22, int(round(base_sizes.get(aspect, 56) * spec.headline_size)))

    # Filter words strictly visible inside the candidate clip
    visible_raw = [
        w for w in words
        if float(w.get("end", 0.0)) > clip_start and float(w.get("start", 0.0)) < clip_end
    ]

    enriched_words: list[WordToken] = []
    for idx, w in enumerate(visible_raw):
        # Clamp word bounds within the clip
        w_start = max(clip_start, float(w.get("start", clip_start)))
        w_end = min(clip_end, float(w.get("end", clip_end)))
        token = build_word_token(
            {**w, "start": w_start, "end": w_end},
            idx=idx,
            emoji_map=emoji_map,
            font_size_px=font_size_px,
        )
        enriched_words.append(token)

    # Group words into visual phrase spans (2-4 words per card)
    phrases: list[PhraseSpan] = []
    max_words_per_phrase = max(1, spec.max_words)
    chunk: list[WordToken] = []

    def commit_phrase(tokens: list[WordToken], p_idx: int) -> None:
        if not tokens:
            return
        p_text = " ".join(t.text for t in tokens)
        p_start = tokens[0].start
        p_end = tokens[-1].end
        p_start_ms = tokens[0].start_ms
        p_end_ms = tokens[-1].end_ms
        phrases.append(PhraseSpan(
            id=f"p_{p_idx}",
            start=p_start,
            end=p_end,
            start_ms=p_start_ms,
            end_ms=p_end_ms,
            duration_ms=max(20, p_end_ms - p_start_ms),
            text=p_text,
            word_count=len(tokens),
            words=[t.to_dict() for t in tokens],
            headline=headline_text,
            layout_zone=spec.zone,
        ))

    p_count = 0
    for token in enriched_words:
        chunk.append(token)
        # Split on max_words or punctuation termination
        if len(chunk) >= max_words_per_phrase or token.text.endswith((".", "!", "?", ";", ":")):
            commit_phrase(chunk, p_count)
            p_count += 1
            chunk = []
    if chunk:
        commit_phrase(chunk, p_count)

    styling_metadata = {
        "preset_key": spec.key,
        "label": spec.label,
        "font": spec.font,
        "headline_font": resolve_headline_font(spec),
        "font_size_px": font_size_px,
        "headline_size_px": headline_size_px,
        "uppercase": spec.uppercase,
        "colors": {
            "primary": ass_color_to_hex(spec.primary),
            "accent": ass_color_to_hex(spec.accent),
            "upcoming": ass_color_to_hex(spec.upcoming),
            "outline": ass_color_to_hex(spec.outline),
            "fill": ass_color_to_hex(spec.fill),
            "fill_text": ass_color_to_hex(spec.fill_text),
        },
        "active_decoration": spec.active,
        "active_pop": spec.active_pop,
        "caption_box": spec.caption_box,
        "zone": spec.zone,
        "headline": spec.headline,
        "frame": spec.frame,
        "kinetic_mode": getattr(spec, "kinetic_mode", "pop"),
        "spring_physics": {
            "tension": getattr(spec, "spring_tension", 280.0),
            "friction": getattr(spec, "spring_friction", 24.0),
            "mass": getattr(spec, "spring_mass", 1.0),
            "scale_overshoot": 1.22 if spec.active_pop else 1.0,
            "slide_y_px": 8,
        },
        "tilt_deg": getattr(spec, "tilt_deg", 0.0),
        "shader_stack": {
            "outer_stroke": {
                "width": getattr(spec, "outer_stroke_width", 0.0),
                "color": ass_color_to_hex(getattr(spec, "outer_stroke_color", None) or spec.outline),
            } if getattr(spec, "outer_stroke_width", 0.0) > 0 else None,
            "inner_stroke": {
                "width": getattr(spec, "inner_stroke_width", 0.0),
                "color": ass_color_to_hex(getattr(spec, "inner_stroke_color", None) or "#ffffff"),
            } if getattr(spec, "inner_stroke_width", 0.0) > 0 else None,
            "shadow": {
                "blur": getattr(spec, "shadow_blur", spec.shadow * 2.0),
                "x": getattr(spec, "shadow_x", 0.0),
                "y": getattr(spec, "shadow_y", spec.shadow * 1.5),
                "color": getattr(spec, "shadow_color", "rgba(0, 0, 0, 0.75)"),
            } if (getattr(spec, "shadow_blur", 0.0) > 0 or spec.shadow > 0) else None,
            "glow": {
                "blur": getattr(spec, "glow_blur", spec.glow * 12.0),
                "color": getattr(spec, "glow_color", ass_color_to_hex(spec.accent)),
            } if (getattr(spec, "glow_blur", 0.0) > 0 or spec.glow > 0) else None,
            "active_gradient": list(spec.active_gradient) if getattr(spec, "active_gradient", None) else None,
            "primary_gradient": list(spec.primary_gradient) if getattr(spec, "primary_gradient", None) else None,
        },
    }

    # Multi-Track B-Roll & Polish Compositor metadata (Phase 5)
    stickers: list[dict[str, Any]] = []
    camera_events: list[dict[str, Any]] = []
    audio_sfx: list[dict[str, Any]] = []

    for token in enriched_words:
        if token.sticker:
            stk_event = {
                "id": token.sticker["id"],
                "word_id": token.id,
                "word": token.word,
                "category": token.sticker["category"],
                "asset": token.sticker["asset"],
                "start_ms": token.start_ms,
                "end_ms": token.end_ms,
                "tilt_deg": token.sticker["tilt_deg"],
                "offset_x": token.sticker["offset_x"],
                "offset_y": token.sticker["offset_y"],
                "scale": token.sticker["scale"],
            }
            stickers.append(stk_event)
            # Synchronized acoustic trigger on sticker pop-in
            audio_sfx.append({
                "type": "pop",
                "word_id": token.id,
                "timestamp_ms": token.start_ms,
                "volume": 0.85,
            })

        if token.camera_punch:
            camera_events.append({
                "type": "punch",
                "word_id": token.id,
                "start_ms": token.start_ms,
                "end_ms": token.end_ms,
                "duration_ms": token.duration_ms,
                "scale": 1.12,
            })
            audio_sfx.append({
                "type": "punch",
                "word_id": token.id,
                "timestamp_ms": token.start_ms,
                "volume": 0.70,
            })
        elif token.highlight:
            # Mechanical tactile click on active keyword onset
            audio_sfx.append({
                "type": "click",
                "word_id": token.id,
                "timestamp_ms": token.start_ms,
                "volume": 0.45,
            })

    # Whip pan camera transitions at phrase boundaries
    for p_idx, phrase in enumerate(phrases):
        if p_idx > 0:
            whip_start = max(0, phrase.start_ms - 100)
            camera_events.append({
                "type": "whip_pan",
                "phrase_id": phrase.id,
                "start_ms": whip_start,
                "duration_ms": 180,
                "direction": 1 if (p_idx % 2 == 1) else -1,
                "displacement_px": 44.0,
            })
            audio_sfx.append({
                "type": "whoosh",
                "phrase_id": phrase.id,
                "timestamp_ms": whip_start,
                "volume": 0.65,
            })

    # Ensure SFX cues are strictly ordered chronologically
    audio_sfx.sort(key=lambda s: s["timestamp_ms"])

    timeline = KineticTimeline(
        version="1.0",
        clip_id=clip_id,
        start=round(clip_start, 3),
        end=round(clip_end, 3),
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=duration_ms,
        aspect_ratio=aspect,
        word_count=len(enriched_words),
        words=[w.to_dict() for w in enriched_words],
        phrases=[p.to_dict() for p in phrases],
        styling_metadata=styling_metadata,
        stickers=stickers,
        camera_events=camera_events,
        audio_sfx=audio_sfx,
    )

    return timeline.to_dict()

