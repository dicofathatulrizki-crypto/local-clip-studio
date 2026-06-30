"""ProgressParser — parses FFmpeg stderr output for real-time progress reporting.

FFmpeg outputs progress information in two formats:
1. Default stderr output (parsed via regex)
2. '-progress' flag output (key=value pairs, more precise)

This parser handles both formats and produces structured progress objects.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class MediaProgress:
    """Current progress state of an FFmpeg operation."""
    frame: int = 0
    fps: float = 0.0
    quality: float = 0.0
    size_kb: int = 0
    time_ms: int = 0
    speed: float = 0.0  # e.g., 1.5x means 1.5x real-time
    bitrate_kbps: float = 0.0
    total_duration_ms: int = 0
    progress: float = 0.0  # 0.0 to 1.0

    @property
    def percent(self) -> float:
        return self.progress * 100.0

    @property
    def time_formatted(self) -> str:
        total_sec = self.time_ms / 1000
        m, s = divmod(int(total_sec), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def to_dict(self) -> dict[str, object]:
        return {
            "frame": self.frame,
            "fps": self.fps,
            "time_ms": self.time_ms,
            "time": self.time_formatted,
            "speed": self.speed,
            "progress": round(self.progress, 4),
            "percent": round(self.percent, 1),
        }


# Callback type for progress updates
ProgressCallback = Callable[[MediaProgress], None]


# Regex patterns for FFmpeg stderr parsing
_FRAME_RE = re.compile(r"frame=\s*(\d+)")
_FPS_RE = re.compile(r"fps=\s*([\d.]+)")
_QUALITY_RE = re.compile(r"q=\s*([\d.-]+)")
_SIZE_RE = re.compile(r"size=\s*(\d+)kB")
_TIME_RE = re.compile(r"time=\s*(\d+):(\d+):(\d+\.\d+)")
_BITRATE_RE = re.compile(r"bitrate=\s*([\d.]+)kb/s")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")

_TIME_MS_RE = re.compile(r"out_time_ms=\s*(\d+)")


class ProgressParser:
    """Parses FFmpeg stderr lines and calls the progress callback.

    Usage:
        parser = ProgressParser(total_duration_ms=600000)
        for line in stderr_lines:
            progress = parser.parse_line(line)
            print(f"Progress: {progress.percent}%")
    """

    def __init__(
        self,
        total_duration_ms: int = 0,
        callback: ProgressCallback | None = None,
    ) -> None:
        self._total = total_duration_ms
        self._callback = callback
        self._last_progress = MediaProgress(total_duration_ms=total_duration_ms)

    def set_duration(self, duration_ms: int) -> None:
        """Set or update the total duration."""
        self._total = duration_ms
        self._last_progress.total_duration_ms = duration_ms

    def parse_line(self, line: str) -> MediaProgress:
        """Parse a single line of FFmpeg stderr output.

        Args:
            line: A line from FFmpeg stderr.

        Returns:
            Updated MediaProgress with parsed values.
        """
        p = self._last_progress

        # Try key=value format first (from -progress flag)
        if "=" in line and not line.startswith("  "):
            # Only use key=value parsing for lines that start with a key (not indented stderr)
            parts = line.strip().split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                raw_value = parts[1].strip()
                # Take only the first token before any space (pure value)
                value = raw_value.split()[0] if raw_value else ""
                try:
                    if key == "frame":
                        p.frame = int(value)
                    elif key == "fps":
                        p.fps = float(value)
                    elif key == "out_time_ms":
                        p.time_ms = int(value) // 1000
                    elif key == "speed":
                        p.speed = float(value.replace("x", ""))
                    elif key == "bitrate":
                        p.bitrate_kbps = float(value.replace("kb/s", ""))
                    elif key == "total_size":
                        p.size_kb = int(value) // 1024
                except (ValueError, IndexError):
                    pass

        # Try regex-based parsing (from default stderr)
        frame_match = _FRAME_RE.search(line)
        if frame_match:
            p.frame = int(frame_match.group(1))

        fps_match = _FPS_RE.search(line)
        if fps_match:
            p.fps = float(fps_match.group(1))

        quality_match = _QUALITY_RE.search(line)
        if quality_match:
            p.quality = float(quality_match.group(1))

        size_match = _SIZE_RE.search(line)
        if size_match:
            p.size_kb = int(size_match.group(1))

        time_match = _TIME_RE.search(line)
        if time_match:
            h, m, s = int(time_match.group(1)), int(time_match.group(2)), float(time_match.group(3))
            p.time_ms = int(h * 3600000 + m * 60000 + s * 1000)

        bitrate_match = _BITRATE_RE.search(line)
        if bitrate_match:
            p.bitrate_kbps = float(bitrate_match.group(1))

        speed_match = _SPEED_RE.search(line)
        if speed_match:
            p.speed = float(speed_match.group(1))

        # Calculate progress
        if self._total > 0:
            p.progress = min(p.time_ms / self._total, 1.0)

        p.total_duration_ms = self._total

        if self._callback:
            self._callback(p)

        return p

    def parse_lines(self, lines: list[str]) -> MediaProgress:
        """Parse multiple lines and return the final progress.

        Args:
            lines: List of stderr lines.

        Returns:
            Final MediaProgress after parsing all lines.
        """
        for line in lines:
            self.parse_line(line)
        return self._last_progress

    @property
    def current(self) -> MediaProgress:
        """Get the current progress state."""
        return self._last_progress

    def reset(self) -> None:
        """Reset the parser to initial state."""
        self._last_progress = MediaProgress(total_duration_ms=self._total)
