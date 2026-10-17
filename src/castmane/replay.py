"""Replay buffer (OBS-style): keep the last N seconds, save on demand.

Minimal crash-safe design on top of the existing ffmpeg core:
- When enabled, a second encoder runs alongside the main recording and
  writes 10s segments (`-f segment -segment_time 10 -segment_wrap K`) with
  fragmented movflags, so every segment stays playable even if killed.
- `save()` picks the newest segments covering `replay_seconds` and
  concatenates them with `ffmpeg -f concat -c copy` (no re-encode).
- `ReplayRecorder` owns that second encoder: it starts with the recording
  and rotates the segment so only the last `replay_seconds` stay on disk.
- All helpers are pure/testable; subprocess calls use arg lists (no shell).
"""
from __future__ import annotations

import math
import signal
import subprocess
import time
from pathlib import Path

from .config import AppConfig
from .recorder import FfmpegX11Recorder, capture_input_args

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
    # A keyframe every SEGMENT_TIME_S: the segment muxer can only cut on a
    # keyframe, and openh264's default GOP is far longer, which produced empty
    # segments (and an empty buffer).
    gop = max(1, _fps_of(video_input_args)) * SEGMENT_TIME_S
    cmd += [
        "-c:v", "libopenh264", "-pix_fmt", "yuv420p",
        "-g", str(gop),
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "segment", "-segment_time", str(SEGMENT_TIME_S),
        "-segment_wrap", str(wrap), "-segment_format", "mp4",
        str(pat),
    ]
    return cmd


def _fps_of(input_args: list[str]) -> int:
    """Frame rate from an ffmpeg input arg list (`-framerate 30 ...`), 30 if absent."""
    for i, arg in enumerate(input_args):
        if arg == "-framerate" and i + 1 < len(input_args):
            try:
                return max(1, int(float(input_args[i + 1])))
            except ValueError:
                break
    return 30


def list_segments(output_dir: Path, prefix: str = "replay") -> list[Path]:
    """Non-empty ring segments, oldest first. MP4 (ffmpeg) and MKV
    (GStreamer, which only muxes Matroska) are both ring members."""
    try:
        target = replay_dir(output_dir)
        if not target.is_dir():
            return []
        found: list[Path] = []
        for pattern in (f"{prefix}_*.mp4", f"{prefix}_*.mkv"):
            found.extend(p for p in target.glob(pattern) if p.is_file())
        return [p for p in sorted(found) if p.stat().st_size > 0]
    except OSError:
        return []


def select_segments_for_save(segments: list[Path], replay_seconds: int) -> list[Path]:
    """Newest segments covering the requested window (oldest-first)."""
    need = max(1, math.ceil(replay_seconds / SEGMENT_TIME_S))
    ordered = sorted(segments)
    return ordered[-need:] if len(ordered) > need else ordered


def build_concat_cmd(segments: list[Path], dest: Path,
                     list_file: Path) -> list[str]:
    """Lossless join of the segments through a concat list file.

    The list must be a real file: the concat demuxer resolves the `file`
    entries relative to the list it read, so feeding the list through
    `pipe:0` makes it look for `pipe:<abs path>` and the join fails.
    """
    return ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(dest)]


def concat_list_text(segments: list[Path]) -> str:
    """Concat demuxer list body, one absolute path per line."""
    return "".join(f"file '{Path(p).as_posix()}'\n" for p in segments)


def save_replay(segments: list[Path], dest: Path) -> bool:
    """Concatenate segments to `dest` with `ffmpeg -c copy`. Never raises."""
    if not segments:
        return False
    list_file = Path(dest).with_suffix(dest.suffix + ".concat.txt")
    cmd = build_concat_cmd(segments, dest, list_file)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        list_file.write_text(concat_list_text(segments), encoding="utf-8")
        r = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            list_file.unlink(missing_ok=True)
        except OSError:
            pass
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def prune_segments(output_dir: Path, keep: int, prefix: str = "replay") -> None:
    """Delete all but the newest `keep` segments. Never raises."""
    if keep <= 0:
        return
    try:
        for old in list_segments(output_dir, prefix)[:-keep]:
            Path(old).unlink(missing_ok=True)
    except OSError:
        pass


class ReplayRecorder:
    """Owns the rolling replay buffer next to a recording.

    - **ffmpeg / X11**: a second ffmpeg process with `-f segment
      -segment_wrap`, which rotates and bounds the ring itself. Started here.
    - **GStreamer / portal**: the encoded stream is teed inside the main
      pipeline into a `multifilesink` ring (`PortalRecorder.build_cmd`), so
      there is no extra process. A second PipeWire consumer cannot read the
      same portal fd, which is why the branch lives in the main pipeline.

    Both cases keep the last `replay_seconds` on disk after the take ends, so
    a moment can still be saved from the tail of the recording.
    """

    def __init__(self, cfg: AppConfig, backend=None) -> None:
        self.cfg = cfg
        self.backend = backend
        self._proc: subprocess.Popen[bytes] | None = None
        self.started_at = 0.0
        self.last_error = ""

    @property
    def active(self) -> bool:
        """True while this recorder owns a replay encoder process. Portal
        recordings write the ring from the main pipeline, so they report
        False here."""
        return self._proc is not None

    @property
    def needs_process(self) -> bool:
        """True when the buffer requires a second encoder process."""
        return isinstance(self.backend, FfmpegX11Recorder)

    def start(self) -> bool:
        """Make sure the buffer is armed. Returns False when it could not be
        set up (the buffer then stays empty instead of breaking the take)."""
        if self._proc is not None or not self.needs_process:
            return True
        args = capture_input_args(self.cfg)
        if not args:
            self.last_error = "no X11 display for the replay buffer"
            return False
        cmd = build_replay_cmd(args, self.cfg.output_dir, self.cfg.replay_seconds)
        try:
            replay_dir(self.cfg.output_dir).mkdir(parents=True, exist_ok=True)
            # DEVNULL, not PIPE: nothing reads this encoder's log, and an
            # unread pipe would fill up and stall it mid-recording.
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except (OSError, ValueError) as e:
            self._proc = None
            self.last_error = str(e)
            return False
        self.last_error = ""
        self.started_at = time.time()
        return True

    def _terminate(self, proc: subprocess.Popen[bytes]) -> None:
        """Same graceful order as the main recorder, so the muxer writes its
        trailer instead of leaving a truncated segment behind."""
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        except OSError:
            pass

    def stop(self) -> None:
        """Tear the encoder down and trim the ring. Safe to call when
        nothing is running (and required after a portal take, where the ring
        was written by the main pipeline)."""
        proc, self._proc = self._proc, None
        if proc is not None:
            self._terminate(proc)
        prune_segments(
            Path(self.cfg.output_dir),
            segment_wrap_count(self.cfg.replay_seconds),
        )
