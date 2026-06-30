"""ThumbnailGenerator — generates video thumbnails at specified timestamps.

Uses FFmpeg to extract single frames as JPEG or PNG images.
Supports custom dimensions, quality, and padding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.process import ProcessRunner
from backend.infrastructure.ffmpeg.types import ThumbnailParams


class ThumbnailGenerator:
    """Generates video thumbnails at specified timestamps.

    Usage:
        generator = ThumbnailGenerator(process_runner, command_builder)
        result = await generator.generate("video.mp4", "thumb.jpg", ThumbnailParams(time_seconds=5.0))
    """

    def __init__(
        self,
        process_runner: ProcessRunner | None = None,
        command_builder: type[CommandBuilder] | None = None,
    ) -> None:
        self._runner = process_runner or ProcessRunner()
        self._builder = command_builder or CommandBuilder

    async def generate(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: ThumbnailParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 30,
    ) -> ThumbnailResult:
        """Generate a thumbnail at the specified time.

        Args:
            input_path: Source video path.
            output_path: Output thumbnail image path.
            params: Thumbnail parameters (time, dimensions, quality).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.

        Returns:
            ThumbnailResult with output path and metadata.

        Raises:
            FFmpegError: On generation failure.
        """
        p = params or ThumbnailParams()
        cmd = self._builder.thumbnail(str(input_path), str(output_path), p)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            retry_count=1,
        )

        out_path = Path(output_path)
        return ThumbnailResult(
            path=str(out_path),
            width=p.width,
            height=p.height,
            size_bytes=out_path.stat().st_size if out_path.exists() else 0,
            time_seconds=p.time_seconds,
            success=result.success,
        )

    async def generate_multiple(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        timestamps: list[float],
        params: ThumbnailParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 60,
    ) -> list[ThumbnailResult]:
        """Generate thumbnails at multiple timestamps.

        Args:
            input_path: Source video path.
            output_dir: Output directory for thumbnails.
            timestamps: List of times in seconds.
            params: Thumbnail parameters.
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time per thumbnail.

        Returns:
            List of ThumbnailResult for each generated thumbnail.
        """
        results: list[ThumbnailResult] = []
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        input_stem = Path(input_path).stem
        for i, ts in enumerate(timestamps):
            output_path = out_dir / f"{input_stem}_thumb_{i:04d}.jpg"
            p = params or ThumbnailParams()
            p.time_seconds = ts
            result = await self.generate(
                input_path, str(output_path), p,
                ffmpeg_path=ffmpeg_path, timeout_seconds=timeout_seconds,
            )
            results.append(result)

        return results


class ThumbnailResult:
    """Result of a thumbnail generation operation."""

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        size_bytes: int,
        time_seconds: float,
        success: bool,
    ) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self.time_seconds = time_seconds
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "time_seconds": self.time_seconds,
            "success": self.success,
        }
