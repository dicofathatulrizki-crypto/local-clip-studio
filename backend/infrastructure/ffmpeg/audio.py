"""AudioExtractor — extracts audio tracks from video files.

Supports multiple output formats (WAV, MP3, AAC, FLAC, Opus),
configurable sample rates, channel counts, and bitrates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.errors import FFmpegError
from backend.infrastructure.ffmpeg.process import ProcessRunner
from backend.infrastructure.ffmpeg.types import AudioParams


class AudioExtractor:
    """Extracts audio from video files.

    Usage:
        extractor = AudioExtractor(process_runner)
        result = await extractor.extract("video.mp4", "audio.wav", AudioParams(sample_rate=16000))
    """

    def __init__(
        self,
        process_runner: ProcessRunner | None = None,
        command_builder: type[CommandBuilder] | None = None,
    ) -> None:
        self._runner = process_runner or ProcessRunner()
        self._builder = command_builder or CommandBuilder

    async def extract(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: AudioParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 300,
        total_duration_ms: int = 0,
    ) -> AudioResult:
        """Extract audio from a video file.

        Args:
            input_path: Source video path.
            output_path: Output audio path.
            params: Audio parameters (codec, sample rate, channels).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.
            total_duration_ms: Total duration for progress tracking.

        Returns:
            AudioResult with output metadata.

        Raises:
            FFmpegError: On extraction failure.
        """
        p = params or AudioParams()
        cmd = self._builder.extract_audio(str(input_path), str(output_path), p)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            total_duration_ms=total_duration_ms,
            retry_count=1,
        )

        out_path = Path(output_path)
        return AudioResult(
            path=str(out_path),
            codec=p.codec,
            sample_rate=p.sample_rate,
            channels=p.channels,
            size_bytes=out_path.stat().st_size if out_path.exists() else 0,
            duration_seconds=result.duration_seconds,
            success=result.success,
        )

    async def extract_audio_stream(
        self,
        input_path: str | Path,
        output_path: str | Path,
        stream_index: int = 0,
        params: AudioParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 300,
    ) -> AudioResult:
        """Extract a specific audio stream by index.

        Args:
            input_path: Source video path.
            output_path: Output audio path.
            stream_index: Audio stream index to extract.
            params: Audio parameters.
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.

        Returns:
            AudioResult with output metadata.
        """
        p = params or AudioParams()
        cmd = [
            "-i", str(input_path),
            "-map", f"0:a:{stream_index}",
            "-vn",
            "-acodec", p.codec,
            "-ar", str(p.sample_rate),
            "-ac", str(p.channels),
            str(output_path),
        ]
        if p.bitrate:
            cmd.insert(-1, "-b:a")
            cmd.insert(-1, p.bitrate)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            retry_count=1,
        )

        out_path = Path(output_path)
        return AudioResult(
            path=str(out_path),
            codec=p.codec,
            sample_rate=p.sample_rate,
            channels=p.channels,
            size_bytes=out_path.stat().st_size if out_path.exists() else 0,
            duration_seconds=result.duration_seconds,
            success=result.success,
        )


class AudioResult:
    """Result of an audio extraction operation."""

    def __init__(
        self,
        path: str,
        codec: str,
        sample_rate: int,
        channels: int,
        size_bytes: int,
        duration_seconds: float,
        success: bool,
    ) -> None:
        self.path = path
        self.codec = codec
        self.sample_rate = sample_rate
        self.channels = channels
        self.size_bytes = size_bytes
        self.duration_seconds = duration_seconds
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "codec": self.codec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "size_bytes": self.size_bytes,
            "duration_seconds": round(self.duration_seconds, 2),
            "success": self.success,
        }
