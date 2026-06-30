"""Unit tests for FFmpegLocator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.ffmpeg.errors import FFmpegNotInstalledError
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities, FFmpegLocator


class TestFFmpegLocator:
    """Tests for FFmpeg binary location and capability detection."""

    def test_init_default(self) -> None:
        """Should initialize without arguments."""
        locator = FFmpegLocator()
        assert locator._ffmpeg_path is None
        assert locator._ffprobe_path is None

    def test_init_with_custom_paths(self) -> None:
        """Should accept custom binary paths."""
        locator = FFmpegLocator(
            ffmpeg_path="/custom/ffmpeg",
            ffprobe_path="/custom/ffprobe",
        )
        assert locator._ffmpeg_path == "/custom/ffmpeg"
        assert locator._ffprobe_path == "/custom/ffprobe"

    def test_ffmpeg_not_found_raises(self) -> None:
        """Should raise FFmpegNotInstalledError when FFmpeg not found."""
        locator = FFmpegLocator()
        with patch("shutil.which", return_value=None):
            with patch("os.path.isfile", return_value=False):
                with pytest.raises(FFmpegNotInstalledError):
                    _ = locator.ffmpeg_path

    def test_is_available_returns_false_when_not_found(self) -> None:
        """Should return False when FFmpeg is not installed."""
        locator = FFmpegLocator()
        assert not locator.is_available()

    def test_parse_version_line(self) -> None:
        """Should extract version string from FFmpeg output."""
        output = "ffmpeg version 6.1.1 Copyright (c) 2000-2023 the FFmpeg developers"
        version = FFmpegLocator._parse_version_line(output)
        assert "6.1.1" in version

    def test_parse_version_line_unknown(self) -> None:
        """Should return 'unknown' when no version found."""
        version = FFmpegLocator._parse_version_line("no version here")
        assert version == "unknown"

    @pytest.mark.parametrize(
        ("version_str", "expected"),
        [
            ("ffmpeg version 6.0", (6, 0, 0)),
            ("ffmpeg version 6.1.1", (6, 1, 1)),
            ("ffmpeg version 7.0", (7, 0, 0)),
            ("ffmpeg version n6.0", (6, 0, 0)),
            ("unknown", (0, 0, 0)),
            ("", (0, 0, 0)),
        ],
    )
    def test_parse_version_tuple(
        self,
        version_str: str,
        expected: tuple[int, int, int],
    ) -> None:
        """Should parse version strings into comparable tuples."""
        result = FFmpegLocator._parse_version_tuple(version_str)
        assert result == expected

    def test_ffmpeg_capabilities_defaults(self) -> None:
        """FFmpegCapabilities should have correct defaults."""
        caps = FFmpegCapabilities()
        assert caps.version == ""
        assert caps.version_tuple == (0, 0, 0)
        assert caps.encoders == []
        assert caps.decoders == []
        assert caps.hw_accels == []
        assert not caps.is_installed

    def test_ffmpeg_capabilities_version_check(self) -> None:
        """is_installed should check minimum version."""
        caps = FFmpegCapabilities(version_tuple=(6, 1, 0))
        assert caps.is_installed

        caps = FFmpegCapabilities(version_tuple=(5, 1, 0))
        assert not caps.is_installed

        caps = FFmpegCapabilities(version_tuple=(0, 0, 0))
        assert not caps.is_installed

    def test_ffmpeg_capabilities_hw_detection(self) -> None:
        """Hardware encoder flags should be set correctly."""
        caps = FFmpegCapabilities(
            hw_encoders=["h264_nvenc", "hevc_nvenc"],
        )
        assert caps.has_nvenc

        caps = FFmpegCapabilities(
            hw_encoders=["h264_amf"],
        )
        assert caps.has_amf

        caps = FFmpegCapabilities(
            hw_encoders=["h264_videotoolbox"],
        )
        assert caps.has_videotoolbox

        caps = FFmpegCapabilities(
            hw_encoders=["h264_vaapi"],
        )
        assert caps.has_vaapi

    def test_check_filter(self) -> None:
        """Should check if a filter is available."""
        locator = FFmpegLocator()
        caps = FFmpegCapabilities(filters=["scale", "crop", "pad"])
        locator._capabilities = caps
        assert locator.check_filter("scale")
        assert locator.check_filter("crop")
        assert not locator.check_filter("nonexistent")

    def test_check_encoder(self) -> None:
        """Should check if an encoder is available."""
        locator = FFmpegLocator()
        caps = FFmpegCapabilities(encoders=["libx264", "h264_nvenc"])
        locator._capabilities = caps
        assert locator.check_encoder("libx264")
        assert locator.check_encoder("h264_nvenc")
        assert not locator.check_encoder("nonexistent")

    def test_get_encoder_list(self) -> None:
        """Should return list of all encoders."""
        locator = FFmpegLocator()
        caps = FFmpegCapabilities(encoders=["libx264", "h264_nvenc", "aac"])
        locator._capabilities = caps
        encoders = locator.get_encoder_list()
        assert "libx264" in encoders
        assert "h264_nvenc" in encoders
        assert len(encoders) == 3
