"""Replay buffer (OBS-style): keep the last N seconds, save on demand.

Minimal crash-safe design on top of the existing ffmpeg core:
- When enabled, a background ffmpeg writes 10s MP4 segments
  (`-f segment -segment_time 10 -segment_wrap K`) with fragmented movflags,
  so every segment stays playable even if killed.
- `save()` picks the newest segments covering `replay_seconds` and
  concatenates them with `ffmpeg -f concat -c copy` (no re-encode).
- All helpers are pure/testable; subprocess calls use arg lists (no shell).
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

SEGMENT_TIME_S = 10


def replay_dir(output_dir: Path) -> Path:
    return Path(output_dir) / ".replay"


def segment_wrap_count(replay_seconds: int) -> int:
    """Ring size: enough 10s slots to cover the window +2 spare."""
    return max(3, math.ceil(max(1, replay_seconds) / SEGMENT_TIME_S) + 2)


def segment_pattern(output_dir: Path, prefix: str = "replay") -> Path:
    return replay_dir(output_dir) / f"{prefix}_%03d.mp4"


def build_replay_cmd(video_input_args: list[str], output_dir: Path,
                     replay_seconds: int, extra_args: list[str] | None = None) -> list[str]:
    """ffmpeg segment command for the rolling window. Caller supplies the
    capture input args (e.g. x11grab); muxing stays fragmented/crash-safe."""
    wrap = segment_wrap_count(replay_seconds)
    pat = segment_pattern(output_dir)
    cmd = ["ffmpeg", "-y", *video_input_args]
    if extra_args:
        cmd += extra_args
    cmd += [
        "-c:v", "libopenh264", "-pix_fmt", "yuv420p",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "segment", "-segment_time", str(SEGMENT_TIME_S),
        "-segment_wrap", str(wrap), "-segment_format", "mp4",
        str(pat),
    ]
    return cmd


def list_segments(output_dir: Path, prefix: str = "replay") -> list[Path]:
    try:
        target = replay_dir(output_dir)
        if not target.is_dir():
            return []
        segs = sorted(p for p in target.glob(f"{prefix}_*.mp4") if p.is_file())
        return [p for p in segs if p.stat().st_size > 0]
    except OSError:
        return []


def select_segments_for_save(segments: list[Path], replay_seconds: int) -> list[Path]:
    """Newest segments covering the requested window (oldest-first)."""
    need = max(1, math.ceil(replay_seconds / SEGMENT_TIME_S))
    ordered = sorted(segments)
    return ordered[-need:] if len(ordered) > need else ordered


def build_concat_cmd(segments: list[Path], dest: Path) -> tuple[list[str], str]:
    """Return (ffmpeg_cmd, concat_list_text) for a lossless join."""
    lines = "".join(f"file '{p.as_posix()}'\n" for p in segments)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-protocol_whitelist", "file,pipe",
           "-i", "pipe:0", "-c", "copy", str(dest)]
    return cmd, lines


def save_replay(segments: list[Path], dest: Path) -> bool:
    """Concatenate segments to `dest` via stdin concat list. Never raises."""
    if not segments:
        return False
    cmd, lines = build_concat_cmd(segments, dest)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(cmd, input=lines.encode(),
                           capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0
