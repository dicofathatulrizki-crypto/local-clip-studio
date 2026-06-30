"""ProcessRunner — manages FFmpeg subprocess lifecycle.

Provides:
- Async execution (run in executor to avoid blocking the event loop)
- Configurable timeout
- Cancellation (SIGTERM → SIGKILL)
- Retry with exponential backoff
- Progress reporting via callback
- Temporary file cleanup on failure
- Structured error handling
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.errors import FFmpegError, FFmpegTimeoutError, translate_error
from backend.infrastructure.ffmpeg.progress import ProgressCallback, ProgressParser
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ProcessRunner:
    """Manages FFmpeg subprocess execution with error handling.

    Usage:
        runner = ProcessRunner()
        result = await runner.run(
            cmd=["-i", "input.mp4", "output.mp4"],
            timeout_seconds=300,
            on_progress=lambda p: print(f"{p.percent}%"),
        )
    """

    DEFAULT_TIMEOUT = 600  # 10 minutes
    MAX_RETRIES = 2
    POLL_INTERVAL = 0.1  # 100ms

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._cancelled = False

    async def run(
        self,
        cmd: list[str],
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int | None = None,
        total_duration_ms: int = 0,
        on_progress: ProgressCallback | None = None,
        retry_count: int = 0,
        cleanup_tmp: bool = True,
    ) -> ProcessResult:
        """Execute an FFmpeg command asynchronously.

        Args:
            cmd: Command arguments (excluding the ffmpeg binary).
            ffmpeg_path: Path to the FFmpeg binary.
            timeout_seconds: Maximum execution time (default: 10 min).
            total_duration_ms: Total duration for progress calculation.
            on_progress: Optional callback for progress updates.
            retry_count: Number of retries on transient failure.
            cleanup_tmp: If True, clean up temp files on failure.

        Returns:
            ProcessResult with stdout, stderr, exit code, and timing.

        Raises:
            FFmpegError: On execution failure.
            FFmpegTimeoutError: On timeout.
            asyncio.CancelledError: On cancellation.
        """
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT
        self._cancelled = False

        full_cmd = [ffmpeg_path] + cmd
        cmd_str = " ".join(full_cmd)
        parser = ProgressParser(total_duration_ms=total_duration_ms, callback=on_progress)

        for attempt in range(retry_count + 1):
            if attempt > 0:
                wait = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying FFmpeg command (attempt {attempt + 1})", extra={"wait": wait})
                await asyncio.sleep(wait)

            start_time = time.monotonic()
            try:
                self._process = await asyncio.create_subprocess_exec(
                    ffmpeg_path,
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Read stderr in background task for progress parsing
                async def read_stderr() -> str:
                    if self._process is None or self._process.stderr is None:
                        return ""
                    stderr_lines: list[str] = []
                    while True:
                        line = await self._process.stderr.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace")
                        stderr_lines.append(decoded)
                        if total_duration_ms > 0 and on_progress:
                            parser.parse_line(decoded)
                    return "".join(stderr_lines)

                async def read_stdout() -> str:
                    if self._process is None or self._process.stdout is None:
                        return ""
                    data = await self._process.stdout.read()
                    return data.decode("utf-8", errors="replace")

                # Run with timeout
                stderr_task = asyncio.create_task(read_stderr())
                stdout_task = asyncio.create_task(read_stdout())

                try:
                    exit_code = await asyncio.wait_for(
                        self._process.wait(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    await self._terminate_process()
                    stderr_output = await stderr_task
                    raise FFmpegTimeoutError(timeout_seconds=timeout, command=cmd_str)

                stdout_output = await stdout_task
                stderr_output = await stderr_task

                duration = time.monotonic() - start_time

                if exit_code != 0:
                    if cleanup_tmp:
                        self._cleanup_output_files(cmd)
                    error = translate_error(exit_code, stderr_output, cmd_str)
                    raise error

                return ProcessResult(
                    stdout=stdout_output,
                    stderr=stderr_output,
                    exit_code=exit_code,
                    duration_seconds=duration,
                    command=cmd_str,
                )

            except (FFmpegTimeoutError, FFmpegError):
                raise

            except Exception as exc:
                if attempt < retry_count:
                    logger.warning(
                        "FFmpeg attempt failed, retrying",
                        extra={"attempt": attempt + 1, "error": str(exc)},
                    )
                    continue
                raise
            finally:
                self._process = None

        # Should not reach here
        msg = "FFmpeg execution failed after all retries"
        raise FFmpegError(msg)

    async def cancel(self) -> None:
        """Cancel the currently running FFmpeg process."""
        self._cancelled = True
        await self._terminate_process()

    @property
    def is_running(self) -> bool:
        """Check if a process is currently running."""
        return self._process is not None and self._process.returncode is None

    # ─── Private ────────────────────────────────────────────────

    async def _terminate_process(self) -> None:
        """Terminate the process gracefully, then force kill."""
        if self._process is None:
            return

        pid = self._process.pid
        if pid is not None:
            logger.info("Terminating FFmpeg process", extra={"pid": pid})
            try:
                os.kill(pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning("FFmpeg did not respond to SIGTERM, sending SIGKILL")
                    os.kill(pid, signal.SIGKILL)
                    await self._process.wait()
            except ProcessLookupError:
                pass  # Already dead

        self._process = None

    def _cleanup_output_files(self, cmd: list[str]) -> None:
        """Clean up output files on failure."""
        for arg in cmd:
            if isinstance(arg, str):
                path = Path(arg)
                if path.exists() and path.suffix in {".mp4", ".mov", ".webm", ".wav", ".jpg", ".png"}:
                    try:
                        path.unlink(missing_ok=True)
                        logger.debug("Cleaned up output file on failure", extra={"path": str(path)})
                    except OSError:
                        pass


class ProcessResult:
    """Result of an FFmpeg process execution."""

    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_seconds: float,
        command: str,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_seconds = duration_seconds
        self.command = command

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 2),
            "stderr_preview": self.stderr[:200] if self.stderr else "",
        }
