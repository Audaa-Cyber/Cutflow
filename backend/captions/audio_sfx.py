"""Deterministic Server-Side Audio SFX Compositor & FFmpeg Filtergraph Generator (Phase 5).

Generates sample-accurate FFmpeg audio filtergraphs using `adelay` and `amix` to
synchronize sound effects (pops, clicks, whooshes, punches) with 1:1 parity to
the frontend Web Audio API preview.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_ffmpeg_sfx_filtergraph(
    audio_sfx: list[dict[str, Any]],
    sfx_dir: Path,
    clip_start_sec: float = 0.0,
    clip_duration_sec: float = 5.0,
    source_audio_label: str = "1:a",
    base_input_index: int = 2,
) -> tuple[list[str], str, str]:
    """Compile audio SFX events into FFmpeg inputs and filtergraph fragments.

    Args:
        audio_sfx: Chronological list of SFX cues from KineticTimeline
        sfx_dir: Directory containing `pop.wav`, `click.wav`, `whoosh.wav`, `punch.wav`
        clip_start_sec: Clip start time in seconds
        clip_duration_sec: Clip duration in seconds
        source_audio_label: Label for incoming source audio stream (default "1:a")
        base_input_index: Starting FFmpeg input index for SFX asset files (default 2)

    Returns:
        tuple of (extra_ffmpeg_inputs, filtergraph_string, output_audio_label)
    """
    clip_start_ms = int(round(clip_start_sec * 1000.0))
    clip_end_ms = clip_start_ms + int(round(clip_duration_sec * 1000.0))

    # Sound assets map to file names
    sfx_files = {
        "pop": sfx_dir / "pop.wav",
        "click": sfx_dir / "click.wav",
        "whoosh": sfx_dir / "whoosh.wav",
        "punch": sfx_dir / "punch.wav",
    }

    # Filter events falling strictly inside this clip window
    valid_events = []
    for ev in audio_sfx:
        t_ms = ev.get("timestamp_ms", 0)
        if clip_start_ms <= t_ms <= clip_end_ms:
            stype = ev.get("type", "pop")
            if stype in sfx_files and sfx_files[stype].is_file():
                valid_events.append(ev)

    if not valid_events:
        # No SFX to mix; passthrough source audio unchanged
        return [], "", source_audio_label

    # Collect unique SFX files to add as FFmpeg inputs
    used_types = sorted(list(set(ev["type"] for ev in valid_events)))
    type_to_input_idx: dict[str, int] = {}
    extra_inputs: list[str] = []

    for idx, stype in enumerate(used_types):
        input_idx = base_input_index + idx
        type_to_input_idx[stype] = input_idx
        extra_inputs.extend(["-i", str(sfx_files[stype])])

    # Build adelay + volume chains for each triggered event
    filter_chains = []
    mix_labels = [f"[{source_audio_label}]"]

    for i, ev in enumerate(valid_events):
        stype = ev["type"]
        input_idx = type_to_input_idx[stype]
        delay_ms = max(0, ev["timestamp_ms"] - clip_start_ms)
        vol = round(float(ev.get("volume", 0.75)), 2)

        out_label = f"sfx_{i}"
        filter_chains.append(
            f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},volume={vol}[{out_label}]"
        )
        mix_labels.append(f"[{out_label}]")

    # Combine source audio with all delayed SFX tracks via amix
    total_inputs = len(mix_labels)
    amix_chain = f"{''.join(mix_labels)}amix=inputs={total_inputs}:dropout_transition=0:normalize=0[aout]"
    filter_chains.append(amix_chain)

    full_filtergraph = ";".join(filter_chains)
    return extra_inputs, full_filtergraph, "[aout]"

