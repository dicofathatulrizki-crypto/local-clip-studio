"""FFmpegErrorTranslator — maps FFmpeg exit codes and stderr to structured exceptions.

Every FFmpeg operation returns structured errors that the service layer
can handle. Raw FFmpeg error output is never exposed to callers.
"""
from __future__ import annotations


class FFmpegError(Exception):
    """Base exception for all FFmpeg-related errors."""

    def __init__(
        self,
        message: str,
        exit_code: int = -1,
        stderr: str = "",
        command: str = "",
    ) -> None:
        self.exit_code = exit_code
        self.stderr = stderr
        self.command = command
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.__class__.__name__,
            "message": str(self),
            "exit_code": self.exit_code,
            "stderr": self.stderr[-500:] if self.stderr else "",
        }


class FFmpegNotInstalledError(FFmpegError):
    """FFmpeg binary not found on the system."""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "FFmpeg not found. Install FFmpeg 6.0+ and ensure it is in PATH.",
            exit_code=-1,
        )


class FFmpegTimeoutError(FFmpegError):
    """FFmpeg process exceeded the configured timeout."""

    def __init__(self, timeout_seconds: int, command: str = "") -> None:
        super().__init__(
            f"FFmpeg timed out after {timeout_seconds}s",
            exit_code=-1,
            command=command,
        )


class FFmpegFormatError(FFmpegError):
    """Unsupported or corrupted media format."""


class FFmpegCodecError(FFmpegError):
    """Unsupported codec or encoder."""


class FFmpegIntegrityError(FFmpegError):
    """Output file validation failed (checksum mismatch, corrupt output)."""


class FFmpegResourceError(FFmpegError):
    """Resource limitation (disk full, memory exhausted)."""


def translate_error(
    exit_code: int,
    stderr: str,
    command: str = "",
) -> FFmpegError:
    """Translate FFmpeg exit code and stderr into a structured exception.

    Args:
        exit_code: FFmpeg process exit code.
        stderr: Standard error output from FFmpeg.
        command: The full FFmpeg command string.

    Returns:
        An appropriate FFmpegError subclass.
    """
    stderr_lower = stderr.lower()

    # Known error patterns
    if exit_code == 127:
        return FFmpegNotInstalledError()

    if "not found" in stderr_lower and ("encoder" in stderr_lower or "decoder" in stderr_lower):
        return FFmpegCodecError(
            f"Unsupported codec: {stderr[:200]}",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    if "unknown format" in stderr_lower or "not a valid" in stderr_lower:
        return FFmpegFormatError(
            f"Unsupported or corrupted format: {stderr[:200]}",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    if "no such file" in stderr_lower or "cannot open" in stderr_lower:
        return FFmpegError(
            f"File not found: {stderr[:200]}",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    if "invalid data found when processing" in stderr_lower:
        return FFmpegIntegrityError(
            f"Corrupted media file: {stderr[:200]}",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    if "no space left" in stderr_lower or "disk full" in stderr_lower:
        return FFmpegResourceError(
            "Insufficient disk space for FFmpeg output",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    if "permission denied" in stderr_lower:
        return FFmpegError(
            f"Permission denied: {stderr[:200]}",
            exit_code=exit_code,
            stderr=stderr,
            command=command,
        )

    # Generic error
    detail = stderr[:300] if stderr else f"Exit code {exit_code}"
    return FFmpegError(
        f"FFmpeg failed: {detail}",
        exit_code=exit_code,
        stderr=stderr,
        command=command,
    )
