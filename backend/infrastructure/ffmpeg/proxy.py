"""ProxyGenerator — generates low-resolution proxy videos for editing workflows.

Creates smaller, lower-resolution copies of source media for performance.
Supports GPU-accelerated encoding via the HAL when available.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.errors import FFmpegError
from backend.infrastructure.ffmpeg.process import ProcessRunner
from backend.infrastructure.ffmpeg.types import ProxyParams


class ProxyGenerator:
    """Generates proxy videos from source media.

    Usage:
        gen = ProxyGenerator(process_runner)
        result = await gen.generate("source.mp4", "proxy.mp4", ProxyParams(width=1280, height=720))
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
        params: ProxyParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 600,
        total_duration_ms: int = 0,
    ) -> ProxyResult:
        """Generate a proxy video.

        Args:
            input_path: Source video path.
            output_path: Output proxy path.
            params: Proxy parameters (dimensions, encoder, quality).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.
            total_duration_ms: Total duration for progress tracking.

        Returns:
            ProxyResult with output metadata.

        Raises:
            FFmpegError: On generation failure.
        """
        p = params or ProxyParams()
        cmd = self._builder.proxy(str(input_path), str(output_path), p)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            total_duration_ms=total_duration_ms,
            retry_count=1,
        )

        out_path = Path(output_path)
        return ProxyResult(
            path=str(out_path),
            width=p.width,
            height=p.height,
            encoder=p.encoder,
            size_bytes=out_path.stat().st_size if out_path.exists() else 0,
            duration_seconds=result.duration_seconds,
            success=result.success,
        )


class ProxyResult:
    """Result of a proxy generation operation."""

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        encoder: str,
        size_bytes: int,
        duration_seconds: float,
        success: bool,
    ) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.encoder = encoder
        self.size_bytes = size_bytes
        self.duration_seconds = duration_seconds
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "encoder": self.encoder,
            "size_bytes": self.size_bytes,
            "duration_seconds": round(self.duration_seconds, 2),
            "success": self.success,
        }
