"""FFprobeService — extracts structured media metadata via FFprobe.

Returns MediaInfo objects with stream details, format info, and duration.
All GPU/probe operations are guarded — if FFprobe is unavailable, methods
return a minimal MediaInfo with available=False.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.errors import FFmpegNotInstalledError
from backend.infrastructure.ffmpeg.types import MediaInfo, MediaStreamInfo


class FFprobeService:
    """Extracts structured metadata from media files via FFprobe.

    Usage:
        probe = FFprobeService(ffprobe_path="/usr/bin/ffprobe")
        info = probe.probe("video.mp4")
        print(info.duration_ms, info.width, info.height)
    """

    def __init__(self, ffprobe_path: str = "ffprobe") -> None:
        self._ffprobe_path = ffprobe_path
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if FFprobe binary is accessible."""
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [self._ffprobe_path, "-version"],
                capture_output=True, text=True, timeout=10,
            )
            self._available = result.returncode == 0
        except Exception:
            self._available = False
        return self._available

    def probe(self, input_path: str | Path) -> MediaInfo:
        """Probe a media file and return structured metadata.

        Args:
            input_path: Path to the media file.

        Returns:
            MediaInfo with all detected streams and format information.

        Raises:
            FFmpegNotInstalledError: If FFprobe is not available.
        """
        if not self.is_available:
            raise FFmpegNotInstalledError("FFprobe is not available")

        cmd = [
            self._ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return MediaInfo(path=str(input_path))
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return MediaInfo(path=str(input_path))

        return self._parse_probe_output(data, str(input_path))

    def probe_format(self, input_path: str | Path) -> dict[str, Any]:
        """Probe only format information (faster, less data).

        Args:
            input_path: Path to the media file.

        Returns:
            Dict with format metadata, or empty dict on failure.
        """
        if not self.is_available:
            return {}

        cmd = [
            self._ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(input_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return {}
            data = json.loads(result.stdout)
            fmt: dict[str, Any] = data.get("format", {})
            return fmt
        except Exception:
            return {}

    def probe_streams(self, input_path: str | Path) -> list[dict[str, Any]]:
        """Probe only stream information.

        Args:
            input_path: Path to the media file.

        Returns:
            List of stream dicts, or empty list on failure.
        """
        if not self.is_available:
            return []

        cmd = [
            self._ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(input_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            streams_list: list[dict[str, Any]] = data.get("streams", [])
            return streams_list
        except Exception:
            return []

    # ─── Private ────────────────────────────────────────────────

    def _parse_probe_output(self, data: dict[str, Any], path: str) -> MediaInfo:
        """Parse FFprobe JSON output into a MediaInfo object."""
        info = MediaInfo(path=path, raw=data)

        fmt = data.get("format", {})
        info.format_name = fmt.get("format_name", "")
        info.format_long = fmt.get("format_long_name", "")
        info.file_size_bytes = int(fmt.get("size", 0))
        info.bitrate = int(fmt.get("bit_rate", 0))

        duration_str = fmt.get("duration", "0")
        try:
            info.duration_ms = int(float(duration_str) * 1000)
        except (ValueError, TypeError):
            info.duration_ms = 0

        streams = data.get("streams", [])
        for stream in streams:
            stream_info = self._parse_stream(stream)
            stream_type = stream_info.codec_type
            if stream_type == "video":
                info.video_streams.append(stream_info)
            elif stream_type == "audio":
                info.audio_streams.append(stream_info)
            elif stream_type == "subtitle":
                info.subtitle_streams.append(stream_info)
            else:
                info.other_streams.append(stream_info)

        return info

    def _parse_stream(self, stream: dict[str, Any]) -> MediaStreamInfo:
        """Parse a single stream dict from FFprobe output."""
        codec_type = stream.get("codec_type", "")
        tags = stream.get("tags", {})

        # Duration
        duration_str = stream.get("duration", "0")
        try:
            duration_ms = int(float(duration_str) * 1000)
        except (ValueError, TypeError):
            duration_ms = 0

        # FPS calculation
        avg_frame_rate = stream.get("avg_frame_rate", "0/1")
        fps = 0.0
        if "/" in avg_frame_rate:
            try:
                num, den = avg_frame_rate.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0

        # Bitrate
        bitrate_str = stream.get("bit_rate", "0")
        try:
            bitrate = int(bitrate_str)
        except (ValueError, TypeError):
            bitrate = 0

        return MediaStreamInfo(
            index=int(stream.get("index", 0)),
            codec_type=codec_type,
            codec=stream.get("codec_name", ""),
            codec_long=stream.get("codec_long_name", ""),
            width=int(stream.get("width", 0)),
            height=int(stream.get("height", 0)),
            fps=fps,
            bitrate=bitrate,
            duration_ms=duration_ms,
            language=tags.get("language", ""),
            pixel_format=stream.get("pix_fmt", ""),
            sample_rate=int(stream.get("sample_rate", 0)),
            channels=int(stream.get("channels", 0)),
            metadata=tags,
        )
