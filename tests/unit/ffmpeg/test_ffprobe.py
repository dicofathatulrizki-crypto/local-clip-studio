"""Unit tests for FFprobeService."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.ffmpeg.errors import FFmpegNotInstalledError
from backend.infrastructure.ffmpeg.ffprobe import FFprobeService


class TestFFprobeService:
    """Tests for FFprobe metadata extraction service."""

    def test_init_default(self) -> None:
        """Should use default ffprobe path."""
        probe = FFprobeService()
        assert probe._ffprobe_path == "ffprobe"

    def test_init_custom_path(self) -> None:
        """Should accept custom ffprobe path."""
        probe = FFprobeService(ffprobe_path="/custom/ffprobe")
        assert probe._ffprobe_path == "/custom/ffprobe"

    def test_is_available_returns_false(self) -> None:
        """Should return False when ffprobe is not available."""
        probe = FFprobeService()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert not probe.is_available

    def test_probe_raises_when_unavailable(self) -> None:
        """Should raise FFmpegNotInstalledError when ffprobe is unavailable."""
        probe = FFprobeService()
        probe._available = False
        with pytest.raises(FFmpegNotInstalledError):
            probe.probe("input.mp4")

    def test_probe_returns_media_info_on_success(self) -> None:
        """Should parse ffprobe JSON output into MediaInfo."""
        probe = FFprobeService()
        probe._available = True
        mock_output = {
            "format": {
                "format_name": "mp4",
                "format_long_name": "QuickTime / MOV",
                "size": "1024000",
                "bit_rate": "2000000",
                "duration": "60.0",
            },
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "codec_long_name": "H.264 / AVC",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                    "bit_rate": "1800000",
                    "duration": "60.0",
                    "pix_fmt": "yuv420p",
                    "tags": {"rotate": "0", "language": "und"},
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "codec_long_name": "AAC (Advanced Audio Codec)",
                    "sample_rate": "48000",
                    "channels": 2,
                    "bit_rate": "192000",
                    "duration": "60.0",
                    "tags": {"language": "eng"},
                },
            ],
        }

        with patch("subprocess.run") as mock_run:
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = json.dumps(mock_output)
                mock_run.return_value = mock_result

                info = probe.probe("input.mp4")

        assert info.path == "input.mp4"
        assert info.format_name == "mp4"
        assert info.duration_ms == 60000
        assert info.bitrate == 2000000
        assert info.file_size_bytes == 1024000
        assert info.has_video
        assert info.has_audio
        assert info.width == 1920
        assert info.height == 1080
        assert abs(info.fps - 29.97) < 0.1
        assert info.video_codec == "h264"
        assert info.audio_codec == "aac"
        assert len(info.video_streams) == 1
        assert len(info.audio_streams) == 1
        assert info.video_streams[0].pixel_format == "yuv420p"
        assert info.audio_streams[0].sample_rate == 48000
        assert info.audio_streams[0].channels == 2

    def test_probe_returns_minimal_on_failure(self) -> None:
        """Should return minimal MediaInfo on probe failure."""
        probe = FFprobeService()
        probe._available = True
        with patch("subprocess.run", side_effect=FileNotFoundError):
            info = probe.probe("input.mp4")
        assert info.path == "input.mp4"
        assert not info.has_video

    def test_probe_with_subprocess_error(self) -> None:
        """Should handle non-zero exit from ffprobe."""
        probe = FFprobeService()
        probe._available = True
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            info = probe.probe("input.mp4")
        assert info.path == "input.mp4"
        assert info.duration_ms == 0

    def test_probe_format_success(self) -> None:
        """Should probe only format information."""
        probe = FFprobeService()
        probe._available = True
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"format": {"format_name": "mp4", "duration": "30.0"}})
            mock_run.return_value = mock_result
            fmt = probe.probe_format("input.mp4")
            assert fmt["format_name"] == "mp4"

    def test_probe_format_unavailable(self) -> None:
        """Should return empty dict when ffprobe is unavailable."""
        probe = FFprobeService()
        probe._available = False
        fmt = probe.probe_format("input.mp4")
        assert fmt == {}

    def test_probe_streams_success(self) -> None:
        """Should probe only stream information."""
        probe = FFprobeService()
        probe._available = True
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"streams": [{"codec_type": "video", "codec_name": "h264"}]})
            mock_run.return_value = mock_result
            streams = probe.probe_streams("input.mp4")
            assert len(streams) == 1
            assert streams[0]["codec_name"] == "h264"

    def test_probe_streams_unavailable(self) -> None:
        """Should return empty list when ffprobe is unavailable."""
        probe = FFprobeService()
        probe._available = False
        streams = probe.probe_streams("input.mp4")
        assert streams == []

    def test_parse_stream_duration_invalid(self) -> None:
        """Should handle invalid duration string."""
        probe = FFprobeService()
        stream = probe._parse_stream({"codec_type": "video", "duration": "not-a-number"})
        assert stream.duration_ms == 0

    def test_parse_stream_fps_invalid(self) -> None:
        """Should handle invalid frame rate string."""
        probe = FFprobeService()
        stream = probe._parse_stream({"codec_type": "video", "avg_frame_rate": "not/valid"})
        assert stream.fps == 0.0

    def test_parse_stream_fps_zero_denominator(self) -> None:
        """Should handle zero denominator in frame rate."""
        probe = FFprobeService()
        stream = probe._parse_stream({"codec_type": "video", "avg_frame_rate": "30/0"})
        assert stream.fps == 0.0

    def test_parse_stream_bitrate_invalid(self) -> None:
        """Should handle invalid bitrate."""
        probe = FFprobeService()
        stream = probe._parse_stream({"codec_type": "video", "bit_rate": "not-a-number"})
        assert stream.bitrate == 0

    def test_probe_with_subtitle_stream(self) -> None:
        """Should parse subtitle streams correctly."""
        probe = FFprobeService()
        mock_output = {
            "format": {"format_name": "mkv"},
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
                {"index": 1, "codec_type": "subtitle", "codec_name": "subrip"},
            ],
        }
        probe._available = True
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(mock_output)
            mock_run.return_value = mock_result
            info = probe.probe("input.mkv")
        assert len(info.subtitle_streams) == 1
        assert info.subtitle_streams[0].codec == "subrip"
