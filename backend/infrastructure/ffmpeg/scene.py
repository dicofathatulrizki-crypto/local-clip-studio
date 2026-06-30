"""SceneExtractionHelper — detects scene changes and splits video at boundaries.

Uses FFmpeg scene detection filter to identify transitions, then
generates split commands for extracting individual scenes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.errors import FFmpegError
from backend.infrastructure.ffmpeg.process import ProcessRunner


class SceneExtractionHelper:
    """Detects scene changes and extracts scene segments.

    Usage:
        helper = SceneExtractionHelper(process_runner)
        scenes = await helper.detect_scenes("video.mp4")
        for scene in scenes:
            print(f"Scene {scene.index}: {scene.start_ms}ms - {scene.end_ms}ms")
    """

    SCENE_DETECT_FILTER = "select='gt(scene,0.4)'"

    def __init__(
        self,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._runner = process_runner or ProcessRunner()

    async def detect_scenes(
        self,
        input_path: str | Path,
        sensitivity: float = 0.4,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 300,
    ) -> list[SceneInfo]:
        """Detect scene changes in a video file.

        Uses the FFmpeg scene detection filter to identify scene
        transitions. Returns a list of SceneInfo objects.

        Args:
            input_path: Source video path.
            sensitivity: Scene change sensitivity (0.1 = high, 1.0 = low).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time.

        Returns:
            List of detected SceneInfo objects.

        Raises:
            FFmpegError: On detection failure.
        """
        filter_expr = f"select='gt(scene,{sensitivity})',showinfo"
        cmd = [
            "-i", str(input_path),
            "-vf", filter_expr,
            "-f", "null",
            "-",
        ]

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

        scenes = self._parse_scene_output(result.stderr)
        return scenes

    def split_command(
        self,
        input_path: str | Path,
        output_pattern: str,
        scenes: list[SceneInfo],
        copy: bool = True,
    ) -> list[list[str]]:
        """Generate FFmpeg commands to split video at scene boundaries.

        Args:
            input_path: Source video path.
            output_pattern: Output path pattern (e.g., 'scene_%03d.mp4').
            scenes: List of SceneInfo from detect_scenes().
            copy: If True, use stream copy (fast, no re-encode).

        Returns:
            List of FFmpeg command argument lists.
        """
        commands: list[list[str]] = []
        for scene in scenes:
            start_sec = scene.start_ms / 1000.0
            duration_sec = (scene.end_ms - scene.start_ms) / 1000.0

            output_path = output_pattern.replace(
                "%{index}", f"{scene.index:03d}"
            ).replace(
                "%{start}", f"{scene.start_ms}"
            )

            cmd = [
                "-ss", f"{start_sec:.3f}",
                "-i", str(input_path),
                "-t", f"{duration_sec:.3f}",
            ]
            if copy:
                cmd.extend(["-c", "copy"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
            cmd.extend(["-y", output_path])
            commands.append(cmd)

        return commands

    def merge_scenes(
        self,
        scenes: list[SceneInfo],
        max_scenes_merge: int = 3,
        min_duration_ms: int = 2000,
    ) -> list[SceneInfo]:
        """Merge short adjacent scenes into longer segments.

        Useful for removing very short scene cuts.

        Args:
            scenes: List of detected scenes.
            max_scenes_merge: Maximum number of scenes to merge.
            min_duration_ms: Minimum duration to keep as separate scene.

        Returns:
            Merged list of SceneInfo.
        """
        if not scenes:
            return []

        merged: list[SceneInfo] = []
        current = scenes[0]

        for scene in scenes[1:]:
            duration = current.end_ms - current.start_ms
            if duration < min_duration_ms and len(merged) + 1 < max_scenes_merge:
                # Merge: extend current scene end
                current = SceneInfo(
                    index=current.index,
                    start_ms=current.start_ms,
                    end_ms=scene.end_ms,
                    score=max(current.score, scene.score),
                )
            else:
                merged.append(current)
                current = scene

        merged.append(current)

        # Re-index
        for i, s in enumerate(merged):
            s.index = i

        return merged

    # ─── Private ────────────────────────────────────────────────

    def _parse_scene_output(self, stderr: str) -> list[SceneInfo]:
        """Parse FFmpeg showinfo output to extract scene change timestamps.

        Args:
            stderr: Stderr output from FFmpeg scene detection.

        Returns:
            List of SceneInfo sorted by start time.
        """
        # Parse timestamps from showinfo output
        # Format: [Parsed_showinfo @ 0x...] n:  123 pts: 456 pts_time:12.345
        time_pattern = re.compile(r"pts_time:([\d.]+)")
        times: list[float] = []

        for line in stderr.split("\n"):
            match = time_pattern.search(line)
            if match:
                times.append(float(match.group(1)))

        if not times:
            return []

        # Convert timestamps to scene segments
        scenes: list[SceneInfo] = []
        for i, ts in enumerate(times):
            start_ms = int(ts * 1000)
            end_ms = int(times[i + 1] * 1000) if i + 1 < len(times) else start_ms + 5000
            scenes.append(SceneInfo(
                index=i,
                start_ms=start_ms,
                end_ms=end_ms,
                score=0.5,  # Default score when only timestamps available
            ))

        return scenes


class SceneInfo:
    """Information about a detected scene."""

    def __init__(
        self,
        index: int,
        start_ms: int,
        end_ms: int,
        score: float = 0.0,
    ) -> None:
        self.index = index
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.duration_ms = end_ms - start_ms
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "score": round(self.score, 3),
        }
