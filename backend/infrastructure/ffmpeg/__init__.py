"""FFmpeg infrastructure layer for video processing.

This is the sole entry point for every FFmpeg operation inside the
application. No other module may invoke FFmpeg directly.

The FFmpeg layer:
- MUST NOT contain business logic
- MUST NOT access repositories
- MUST NOT call API routes
- MUST NOT know about clips
- MUST ONLY expose reusable infrastructure services
"""
from __future__ import annotations

from backend.infrastructure.ffmpeg.audio import AudioExtractor, AudioParams, AudioResult
from backend.infrastructure.ffmpeg.errors import (
    FFmpegCodecError,
    FFmpegError,
    FFmpegFormatError,
    FFmpegIntegrityError,
    FFmpegNotInstalledError,
    FFmpegResourceError,
    FFmpegTimeoutError,
    translate_error,
)
from backend.infrastructure.ffmpeg.export import ExportEncoder, ExportParams, ExportResult, GpuEncoderSelector
from backend.infrastructure.ffmpeg.ffprobe import FFprobeService
from backend.infrastructure.ffmpeg.frame import FrameExtractor, FrameExtractParams, FrameResult
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities, FFmpegLocator
from backend.infrastructure.ffmpeg.manager import FFmpegManager
from backend.infrastructure.ffmpeg.process import ProcessResult, ProcessRunner
from backend.infrastructure.ffmpeg.progress import MediaProgress, ProgressParser
from backend.infrastructure.ffmpeg.proxy import ProxyGenerator, ProxyParams, ProxyResult
from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper, SceneInfo
from backend.infrastructure.ffmpeg.thumbnail import ThumbnailGenerator, ThumbnailParams, ThumbnailResult
from backend.infrastructure.ffmpeg.types import (
    AudioParams as AudioParamsType,
    CropParams,
    ExportParams as ExportParamsType,
    FrameExtractParams as FrameExtractParamsType,
    MediaInfo,
    MediaStreamInfo,
    ProxyParams as ProxyParamsType,
    ThumbnailParams as ThumbnailParamsType,
    VideoFilters,
)
from backend.infrastructure.ffmpeg.video_info import VideoInfoExtractor

__all__ = [
    "AudioExtractor",
    "AudioParams",
    "AudioResult",
    "AudioParamsType",
    "CropParams",
    "ExportEncoder",
    "ExportParams",
    "ExportResult",
    "ExportParamsType",
    "FFmpegCapabilities",
    "FFmpegCodecError",
    "FFmpegError",
    "FFmpegFormatError",
    "FFmpegIntegrityError",
    "FFmpegLocator",
    "FFmpegManager",
    "FFmpegNotInstalledError",
    "FFmpegResourceError",
    "FFmpegTimeoutError",
    "FFprobeService",
    "FrameExtractor",
    "FrameExtractParams",
    "FrameResult",
    "FrameExtractParamsType",
    "GpuEncoderSelector",
    "MediaInfo",
    "MediaProgress",
    "MediaStreamInfo",
    "ProcessResult",
    "ProcessRunner",
    "ProgressParser",
    "ProxyGenerator",
    "ProxyParams",
    "ProxyResult",
    "ProxyParamsType",
    "SceneExtractionHelper",
    "SceneInfo",
    "ThumbnailGenerator",
    "ThumbnailParams",
    "ThumbnailResult",
    "ThumbnailParamsType",
    "VideoFilters",
    "VideoInfoExtractor",
    "translate_error",
]
