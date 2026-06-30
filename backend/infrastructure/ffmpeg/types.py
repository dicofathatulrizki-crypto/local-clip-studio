"""Data types for FFmpeg command parameters and configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioParams:
    """Parameters for audio extraction."""
    codec: str = "pcm_s16le"
    sample_rate: int = 16000
    channels: int = 1
    bitrate: str | None = None


@dataclass
class FrameExtractParams:
    """Parameters for frame extraction."""
    fps: float = 1.0
    quality: int = 2  # 1-31, lower is better
    max_count: int | None = None


@dataclass
class ThumbnailParams:
    """Parameters for thumbnail generation."""
    time_seconds: float = 1.0
    width: int = 1280
    height: int = 720
    quality: int = 2
    pad: bool = True


@dataclass
class ProxyParams:
    """Parameters for proxy video generation."""
    width: int = 1280
    height: int = 720
    encoder: str = "libx264"
    crf: int = 23
    preset: str = "fast"
    pad: bool = False


@dataclass
class CropParams:
    """Parameters for video cropping."""
    width: int = 1920
    height: int = 1080
    x: int = 0
    y: int = 0


@dataclass
class ExportParams:
    """Parameters for export encoding."""
    video_encoder: str = "libx264"
    audio_encoder: str = "aac"
    audio_bitrate: str = "192k"
    preset: str = "medium"
    bitrate: str | None = None
    crf: int | None = 23
    pixel_format: str | None = "yuv420p"
    profile: str | None = None
    scale: tuple[int, int] | None = None
    video_filters: str | None = None
    gpu_params: list[str] = field(default_factory=list)


@dataclass
class VideoFilters:
    """Video filter chain configuration."""
    scale: tuple[int, int] | None = None
    crop: CropParams | None = None
    pad: tuple[int, int] | None = None
    fps: float | None = None
    flip_h: bool = False
    flip_v: bool = False
    rotate: float | None = None  # degrees
    custom: str | None = None


@dataclass
class MediaStreamInfo:
    """Information about a single media stream."""
    index: int = 0
    codec_type: str = ""
    codec: str = ""
    codec_long: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bitrate: int = 0
    duration_ms: int = 0
    language: str = ""
    pixel_format: str = ""
    sample_rate: int = 0
    channels: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaInfo:
    """Complete media file information."""
    path: str = ""
    file_size_bytes: int = 0
    duration_ms: int = 0
    bitrate: int = 0
    format_name: str = ""
    format_long: str = ""
    video_streams: list[MediaStreamInfo] = field(default_factory=list)
    audio_streams: list[MediaStreamInfo] = field(default_factory=list)
    subtitle_streams: list[MediaStreamInfo] = field(default_factory=list)
    other_streams: list[MediaStreamInfo] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return len(self.video_streams) > 0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def width(self) -> int:
        return self.video_streams[0].width if self.video_streams else 0

    @property
    def height(self) -> int:
        return self.video_streams[0].height if self.video_streams else 0

    @property
    def fps(self) -> float:
        return self.video_streams[0].fps if self.video_streams else 0.0

    @property
    def video_codec(self) -> str:
        return self.video_streams[0].codec if self.video_streams else ""

    @property
    def audio_codec(self) -> str:
        return self.audio_streams[0].codec if self.audio_streams else ""
