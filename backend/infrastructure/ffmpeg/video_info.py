"""VideoInfoExtractor — convenience wrapper around FFprobeService.

Provides high-level queries for common video properties:
- Resolution, FPS, codec detection
- Bitrate analysis
- Aspect ratio calculation
- Rotated dimension detection
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.ffprobe import FFprobeService
from backend.infrastructure.ffmpeg.types import MediaInfo


class VideoInfoExtractor:
    """Extracts and computes video metadata via FFprobe.

    Usage:
        extractor = VideoInfoExtractor(probe_service)
        info = extractor.get_info("video.mp4")
        print(info.width, info.height, info.fps, info.video_codec)
    """

    def __init__(self, probe_service: FFprobeService | None = None) -> None:
        self._probe = probe_service or FFprobeService()

    def get_info(self, input_path: str | Path) -> MediaInfo:
        """Get full media information.

        Args:
            input_path: Path to the media file.

        Returns:
            MediaInfo with all stream information.
        """
        return self._probe.probe(input_path)

    def get_resolution(self, input_path: str | Path) -> tuple[int, int]:
        """Get video resolution (width, height).

        Accounts for display rotation metadata.

        Args:
            input_path: Path to the media file.

        Returns:
            (width, height) tuple.
        """
        info = self._probe.probe(input_path)
        if not info.video_streams:
            return (0, 0)
        stream = info.video_streams[0]
        # Check for rotation metadata
        rotation = stream.metadata.get("rotate", "0")
        try:
            rot = int(rotation)
        except (ValueError, TypeError):
            rot = 0
        if rot in (90, 270):
            return (stream.height, stream.width)
        return (stream.width, stream.height)

    def get_fps(self, input_path: str | Path) -> float:
        """Get video frame rate.

        Args:
            input_path: Path to the media file.

        Returns:
            Frames per second, or 0.0 if unavailable.
        """
        info = self._probe.probe(input_path)
        return info.fps

    def get_duration_ms(self, input_path: str | Path) -> int:
        """Get video duration in milliseconds.

        Args:
            input_path: Path to the media file.

        Returns:
            Duration in milliseconds, or 0 if unavailable.
        """
        info = self._probe.probe(input_path)
        return info.duration_ms

    def get_codec(self, input_path: str | Path) -> str:
        """Get video codec name.

        Args:
            input_path: Path to the media file.

        Returns:
            Codec name (e.g., 'h264', 'hevc'), or '' if unavailable.
        """
        info = self._probe.probe(input_path)
        return info.video_codec

    def has_audio(self, input_path: str | Path) -> bool:
        """Check if the media file has an audio stream.

        Args:
            input_path: Path to the media file.

        Returns:
            True if an audio stream is detected.
        """
        info = self._probe.probe(input_path)
        return info.has_audio

    def get_aspect_ratio(self, input_path: str | Path) -> float:
        """Calculate display aspect ratio.

        Args:
            input_path: Path to the media file.

        Returns:
            Aspect ratio (width/height), or 0.0 if unavailable.
        """
        width, height = self.get_resolution(input_path)
        if height == 0:
            return 0.0
        return width / height

    def estimate_bitrate_required(
        self,
        resolution: tuple[int, int],
        fps: float,
        quality: str = "standard",
    ) -> int:
        """Estimate the bitrate needed for acceptable quality.

        Args:
            resolution: (width, height) tuple.
            fps: Frames per second.
            quality: 'high', 'standard', 'web', or 'proxy'.

        Returns:
            Estimated bitrate in bits per second.
        """
        pixels = resolution[0] * resolution[1]
        factors = {
            "high": 0.15,
            "standard": 0.08,
            "web": 0.04,
            "proxy": 0.02,
        }
        factor = factors.get(quality, 0.08)
        fps_factor = max(fps / 30.0, 0.5)
        return int(pixels * factor * fps_factor)

    def to_dict(self, input_path: str | Path) -> dict[str, Any]:
        """Get all video metadata as a serializable dict.

        Args:
            input_path: Path to the media file.

        Returns:
            Dict with resolution, fps, duration, codec, aspect_ratio, etc.
        """
        info = self._probe.probe(input_path)
        return {
            "path": str(input_path),
            "duration_ms": info.duration_ms,
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "video_codec": info.video_codec,
            "audio_codec": info.audio_codec,
            "has_audio": info.has_audio,
            "aspect_ratio": round(self.get_aspect_ratio(input_path), 4),
            "format": info.format_name,
            "file_size_bytes": info.file_size_bytes,
        }
