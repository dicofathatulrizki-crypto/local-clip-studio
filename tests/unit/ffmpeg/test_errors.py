"""Unit tests for FFmpeg error translation."""
from __future__ import annotations

import pytest

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


class TestFFmpegErrors:
    """Tests for FFmpeg error classes and translation."""

    def test_base_error(self) -> None:
        """Should store exit code, stderr, and command."""
        err = FFmpegError("test error", exit_code=1, stderr="stderr text", command="ffmpeg -i in out")
        assert err.exit_code == 1
        assert err.stderr == "stderr text"
        assert err.command == "ffmpeg -i in out"
        assert str(err) == "test error"

    def test_base_error_to_dict(self) -> None:
        """Should serialize error to dict."""
        err = FFmpegError("test", exit_code=1, stderr="error output")
        d = err.to_dict()
        assert d["error"] == "FFmpegError"
        assert d["message"] == "test"
        assert d["exit_code"] == 1

    def test_not_installed_error(self) -> None:
        """Should have appropriate default message."""
        err = FFmpegNotInstalledError()
        assert "FFmpeg not found" in str(err)
        assert err.exit_code == -1

    def test_not_installed_custom_message(self) -> None:
        """Should accept custom message."""
        err = FFmpegNotInstalledError("Custom message")
        assert str(err) == "Custom message"

    def test_timeout_error(self) -> None:
        """Should include timeout in message."""
        err = FFmpegTimeoutError(timeout_seconds=300)
        assert "300" in str(err)
        assert err.exit_code == -1

    def test_format_error(self) -> None:
        """Should inherit from FFmpegError."""
        err = FFmpegFormatError("Bad format", exit_code=1)
        assert isinstance(err, FFmpegError)
        assert "Bad format" in str(err)

    def test_codec_error(self) -> None:
        """Should inherit from FFmpegError."""
        err = FFmpegCodecError("Bad codec", exit_code=1)
        assert isinstance(err, FFmpegError)

    def test_integrity_error(self) -> None:
        """Should inherit from FFmpegError."""
        err = FFmpegIntegrityError("Corrupt file", exit_code=1)
        assert isinstance(err, FFmpegError)

    def test_resource_error(self) -> None:
        """Should inherit from FFmpegError."""
        err = FFmpegResourceError("No space", exit_code=1)
        assert isinstance(err, FFmpegError)

    def test_translate_exit_127(self) -> None:
        """Exit code 127 should map to FFmpegNotInstalledError."""
        err = translate_error(127, "")
        assert isinstance(err, FFmpegNotInstalledError)

    def test_translate_encoder_not_found(self) -> None:
        """Should detect missing encoder in stderr."""
        err = translate_error(1, "encoder 'h264_nvenc' not found")
        assert isinstance(err, FFmpegCodecError)

    def test_translate_unknown_format(self) -> None:
        """Should detect unknown format in stderr."""
        err = translate_error(1, "Unknown format")
        assert isinstance(err, FFmpegFormatError)

    def test_translate_corrupt_media(self) -> None:
        """Should detect corrupt media in stderr."""
        err = translate_error(1, "Invalid data found when processing input")
        assert isinstance(err, FFmpegIntegrityError)

    def test_translate_disk_full(self) -> None:
        """Should detect disk full in stderr."""
        err = translate_error(1, "No space left on device")
        assert isinstance(err, FFmpegResourceError)

    def test_translate_permission_denied(self) -> None:
        """Should detect permission denied in stderr."""
        err = translate_error(1, "Permission denied")
        assert isinstance(err, FFmpegError)

    def test_translate_file_not_found(self) -> None:
        """Should detect missing file in stderr."""
        err = translate_error(1, "No such file or directory")
        assert isinstance(err, FFmpegError)

    def test_translate_generic_error(self) -> None:
        """Unknown errors should map to base FFmpegError."""
        err = translate_error(255, "some weird error")
        assert isinstance(err, FFmpegError)
        assert err.exit_code == 255

    def test_translate_with_command(self) -> None:
        """Should include command in translated error."""
        err = translate_error(1, "error", command="ffmpeg -i in out")
        assert err.command == "ffmpeg -i in out"

    def test_stderr_truncated_in_to_dict(self) -> None:
        """Long stderr should be truncated in to_dict."""
        long_stderr = "x" * 1000
        err = FFmpegError("test", exit_code=1, stderr=long_stderr)
        d = err.to_dict()
        assert len(str(d["stderr"])) <= 500
