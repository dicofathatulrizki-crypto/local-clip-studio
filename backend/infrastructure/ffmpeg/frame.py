"""FrameExtractor — extracts video frames as image sequences.

Supports configurable FPS, quality, max count, and output format.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.process import ProcessRunner
from backend.infrastructure.ffmpeg.types import FrameExtractParams


class FrameExtractor:
    """Extracts frames from video files as images.

    Usage:
        extractor = FrameExtractor(process_runner)
        results = await extractor.extract("video.mp4", "/output/frames/", FrameExtractParams(fps=0.5))
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
        output_dir: str | Path,
        params: FrameExtractParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 600,
    ) -> list[FrameResult]:
        """Extract frames from a video file.

        Args:
            input_path: Source video path.
            output_dir: Directory to write frame images.
            params: Frame extraction parameters (FPS, quality, max count).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.

        Returns:
            List of FrameResult for each extracted frame.

        Raises:
            FFmpegError: On extraction failure.
        """
        p = params or FrameExtractParams()
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        output_pattern = str(out_dir / "frame_%05d.jpg")

        cmd = self._builder.extract_frames(str(input_path), output_pattern, p)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            retry_count=1,
        )

        # Collect extracted frames
        frames: list[FrameResult] = []
        for f in sorted(out_dir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png") and f.stem.startswith("frame_"):
                frames.append(FrameResult(
                    path=str(f),
                    frame_number=len(frames),
                    width=0,  # Would require probing individual images
                    height=0,
                    size_bytes=f.stat().st_size,
                    success=True,
                ))

        if not frames and result.success:
            # The output pattern didn't match, but FFmpeg succeeded
            pass

        return frames


class FrameResult:
    """Result of a single frame extraction operation."""

    def __init__(
        self,
        path: str,
        frame_number: int,
        width: int,
        height: int,
        size_bytes: int,
        success: bool,
    ) -> None:
        self.path = path
        self.frame_number = frame_number
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "frame_number": self.frame_number,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "success": self.success,
        }
