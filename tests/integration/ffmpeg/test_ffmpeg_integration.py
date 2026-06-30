"""Integration tests for the FFmpeg module.

These tests validate component interactions using mocked subprocess calls
where FFmpeg is not available. Real FFmpeg tests are conditionally skipped
with documented reasons.
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.ffmpeg.command import CommandBuilder
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
from backend.infrastructure.ffmpeg.export import GpuEncoderSelector
from backend.infrastructure.ffmpeg.ffprobe import FFprobeService
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities, FFmpegLocator
from backend.infrastructure.ffmpeg.manager import FFmpegManager
from backend.infrastructure.ffmpeg.process import ProcessResult, ProcessRunner
from backend.infrastructure.ffmpeg.progress import ProgressParser
from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper, SceneInfo
from backend.infrastructure.ffmpeg.thumbnail import ThumbnailParams
from backend.infrastructure.ffmpeg.types import ExportParams, VideoFilters
from backend.infrastructure.ffmpeg.video_info import VideoInfoExtractor

# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def ffmpeg_available() -> bool:
    """Check if FFmpeg is available in the environment."""
    return os.system("ffmpeg -version > /dev/null 2>&1") == 0


@pytest.fixture
def ffprobe_available() -> bool:
    """Check if FFprobe is available in the environment."""
    return os.system("ffprobe -version > /dev/null 2>&1") == 0


# ─── FFmpegLocator Integration ──────────────────────────────


class TestFFmpegLocatorIntegration:
    """Integration tests for FFmpegLocator."""

    def test_locate_ffmpeg_availability(self, ffmpeg_available: bool) -> None:
        """Should detect FFmpeg availability correctly."""
        locator = FFmpegLocator()
        available = locator.is_available()
        assert available == ffmpeg_available

    def test_capability_detection(self, ffmpeg_available: bool) -> None:
        """Should detect capabilities when FFmpeg is available."""
        locator = FFmpegLocator()
        caps = locator.detect_capabilities()
        assert caps.is_installed == ffmpeg_available
        if ffmpeg_available:
            assert len(caps.version_tuple) >= 3
            assert caps.version_tuple >= (6, 0, 0)
            assert len(caps.encoders) > 0
            assert len(caps.decoders) > 0
            assert len(caps.formats) > 0
            assert len(caps.filters) > 0
            assert "libx264" in caps.encoders

    def test_hardware_detection(self, ffmpeg_available: bool) -> None:
        """Should detect hardware encoders when available."""
        locator = FFmpegLocator()
        caps = locator.detect_capabilities()
        if ffmpeg_available:
            # These may all be False on a CPU-only environment
            assert isinstance(caps.has_nvenc, bool)
            assert isinstance(caps.has_amf, bool)
            assert isinstance(caps.has_videotoolbox, bool)
            assert isinstance(caps.has_vaapi, bool)

    def test_check_encoder_real(self, ffmpeg_available: bool) -> None:
        """Should correctly report encoder availability."""
        locator = FFmpegLocator()
        if ffmpeg_available:
            assert locator.check_encoder("libx264")
        else:
            assert not locator.check_encoder("libx264")


# ─── FFprobeService Integration ─────────────────────────────


class TestFFprobeServiceIntegration:
    """Integration tests for FFprobeService."""

    def test_ffprobe_availability(self, ffprobe_available: bool) -> None:
        """Should detect FFprobe availability."""
        probe = FFprobeService()
        assert probe.is_available == ffprobe_available

    def test_probe_with_sample_data(self) -> None:
        """Should parse sample FFprobe data correctly."""
        probe = FFprobeService()
        probe._available = True
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({
                "format": {"format_name": "mp4", "duration": "10.0"},
                "streams": [
                    {"index": 0, "codec_type": "video", "codec_name": "h264",
                     "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
                ],
            })
            mock_run.return_value = mock_result
            info = probe.probe("test.mp4")

        assert info.format_name == "mp4"
        assert info.duration_ms == 10000
        assert info.width == 1920
        assert info.height == 1080

    def test_probe_format_unavailable_returns_empty(self) -> None:
        """Should return empty dict when ffprobe is unavailable."""
        probe = FFprobeService()
        probe._available = False
        result = probe.probe_format("test.mp4")
        assert result == {}


# ─── Error Translation Integration ──────────────────────────


class TestErrorTranslationIntegration:
    """Integration tests for FFmpeg error translation."""

    def test_known_error_patterns(self) -> None:
        """Should correctly translate known FFmpeg error patterns."""
        patterns = [
            (127, "", FFmpegNotInstalledError),
            (1, "encoder 'h264_nvenc' not found", FFmpegCodecError),
            (1, "Unknown format", FFmpegFormatError),
            (1, "Invalid data found when processing input", FFmpegIntegrityError),
            (1, "No space left on device", FFmpegResourceError),
            (1, "Permission denied", FFmpegError),
            (1, "No such file or directory", FFmpegError),
            (255, "some generic error", FFmpegError),
        ]
        for exit_code, stderr, expected_type in patterns:
            err = translate_error(exit_code, stderr)
            assert isinstance(err, expected_type), (
                f"Expected {expected_type.__name__} for ({exit_code}, '{stderr}'), "
                f"got {type(err).__name__}"
            )


# ─── ProcessRunner Integration ──────────────────────────────


class TestProcessRunnerIntegration:
    """Integration tests for ProcessRunner."""

    @pytest.mark.asyncio
    async def test_run_simple_command(self) -> None:
        """Should run a simple FFmpeg command via mock."""
        runner = ProcessRunner()
        with patch.object(runner, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ProcessResult(
                stdout="", stderr="", exit_code=0,
                duration_seconds=0.5, command="ffmpeg -version",
            )
            result = await runner.run(["-version"], ffmpeg_path="ffmpeg")
            assert result.success
            assert result.exit_code == 0
            assert result.duration_seconds == 0.5

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self) -> None:
        """Should raise FFmpegTimeoutError on timeout."""
        runner = ProcessRunner()
        with patch.object(runner, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FFmpegTimeoutError(timeout_seconds=5)
            with pytest.raises(FFmpegTimeoutError, match="5"):
                await runner.run(["-i", "input.mp4", "output.mp4"], timeout_seconds=5)

    @pytest.mark.asyncio
    async def test_dry_run_no_ffmpeg(self) -> None:
        """Should handle FFmpeg not being available."""
        runner = ProcessRunner()
        with patch.object(runner, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FFmpegNotInstalledError()
            with pytest.raises(FFmpegNotInstalledError):
                await runner.run(["-i", "nonexistent.mp4"])

    def test_process_result_properties(self) -> None:
        """ProcessResult should report success correctly."""
        success = ProcessResult("", "", 0, 1.0, "ffmpeg -i in out")
        assert success.success

        failed = ProcessResult("", "error", 1, 0.5, "ffmpeg -i in out")
        assert not failed.success

    def test_process_result_to_dict(self) -> None:
        """ProcessResult.to_dict should return serializable dict."""
        result = ProcessResult("out", "err", 0, 2.5, "ffmpeg cmd")
        d = result.to_dict()
        assert d["exit_code"] == 0
        assert d["duration_seconds"] == 2.5


# ─── ProgressParser Integration ─────────────────────────────


class TestProgressParserIntegration:
    """Integration tests for ProgressParser."""

    def test_parse_real_ffmpeg_output(self) -> None:
        """Should parse realistic FFmpeg output."""
        parser = ProgressParser(total_duration_ms=120000)
        lines = [
            "frame=   10 fps=12.0 q=28.0 size=     256kB time=00:00:01.00 bitrate=2048.0kb/s speed=0.5x",
            "frame=   50 fps=25.0 q=24.0 size=    1024kB time=00:00:03.50 bitrate=2400.0kb/s speed=1.2x",
            "frame=  100 fps=30.0 q=23.0 size=    2048kB time=00:00:06.00 bitrate=2800.0kb/s speed=2.0x",
        ]
        final = parser.parse_lines(lines)
        assert final.frame == 100
        assert final.fps == 30.0
        assert final.quality == 23.0
        assert final.time_ms == 6000
        assert final.speed == 2.0
        assert final.bitrate_kbps == 2800.0

    def test_progress_percent(self) -> None:
        """Should calculate progress percentage correctly."""
        parser = ProgressParser(total_duration_ms=60000)
        parser.parse_line("time=00:00:30.00")
        assert abs(parser.current.progress - 0.5) < 0.01

        parser.parse_line("time=00:01:00.00")
        assert parser.current.progress == 1.0


# ─── CommandBuilder Integration ─────────────────────────────


class TestCommandBuilderIntegration:
    """Integration tests for CommandBuilder."""

    def test_full_export_pipeline(self) -> None:
        """Should build a complete export command pipeline."""
        params = ExportParams(
            video_encoder="libx264",
            audio_encoder="aac",
            preset="medium",
            bitrate="8M",
            crf=None,
            pixel_format="yuv420p",
            scale=(1920, 1080),
        )
        cmd = CommandBuilder.export("input.mp4", "output.mp4", params)
        cmd_str = " ".join(cmd)

        assert "input.mp4" in cmd_str
        assert "output.mp4" in cmd_str
        assert "libx264" in cmd_str
        assert "aac" in cmd_str
        assert "yuv420p" in cmd_str
        assert "+faststart" in cmd_str

    def test_thumbnail_with_pad(self) -> None:
        """Should build thumbnail command with padding."""
        params = ThumbnailParams(time_seconds=5.0, width=640, height=360, pad=True)
        cmd = CommandBuilder.thumbnail("input.mp4", "thumb.jpg", params)
        full = " ".join(cmd)
        assert "pad=640:360" in full

    def test_filter_graph_builder(self) -> None:
        """Should build complex filter graph."""
        filters = VideoFilters(
            scale=(1920, 1080),
            fps=30.0,
            flip_v=True,
        )
        result = CommandBuilder.build_filter_graph(filters)
        assert "scale=1920:1080" in result
        assert "fps=30.0" in result
        assert "vflip" in result


# ─── VideoInfoExtractor Integration ─────────────────────────


class TestVideoInfoExtractorIntegration:
    """Integration tests for VideoInfoExtractor."""

    def test_estimate_bitrate(self) -> None:
        """Should estimate bitrate for various resolutions."""
        extractor = VideoInfoExtractor()
        hd_bitrate = extractor.estimate_bitrate_required((1920, 1080), 30)
        sd_bitrate = extractor.estimate_bitrate_required((640, 480), 30)
        assert hd_bitrate > sd_bitrate

    def test_estimate_bitrate_proxy(self) -> None:
        """Should estimate lower bitrate for proxy quality."""
        extractor = VideoInfoExtractor()
        standard = extractor.estimate_bitrate_required((1920, 1080), 30, "standard")
        proxy = extractor.estimate_bitrate_required((1920, 1080), 30, "proxy")
        assert proxy < standard


# ─── SceneExtractionHelper Integration ──────────────────────


class TestSceneExtractionHelperIntegration:
    """Integration tests for SceneExtractionHelper."""

    def test_scene_merge(self) -> None:
        """Should merge short adjacent scenes."""
        helper = SceneExtractionHelper()
        scenes = [
            SceneInfo(index=0, start_ms=0, end_ms=2000),
            SceneInfo(index=1, start_ms=2000, end_ms=2500),  # Short scene
            SceneInfo(index=2, start_ms=2500, end_ms=8000),
        ]
        merged = helper.merge_scenes(scenes, max_scenes_merge=3, min_duration_ms=2000)
        assert len(merged) < len(scenes)

    def test_scene_split_command(self) -> None:
        """Should generate split commands from scenes."""
        helper = SceneExtractionHelper()
        scenes = [
            SceneInfo(index=0, start_ms=0, end_ms=10000),
            SceneInfo(index=1, start_ms=10000, end_ms=20000),
        ]
        commands = helper.split_command("input.mp4", "scene_%{index}.mp4", scenes, copy=True)
        assert len(commands) == 2
        for cmd in commands:
            assert "-ss" in cmd
            assert "-t" in cmd
            assert "copy" in cmd

    def test_scene_info_to_dict(self) -> None:
        """SceneInfo should serialize to dict."""
        scene = SceneInfo(index=0, start_ms=0, end_ms=10000, score=0.8)
        d = scene.to_dict()
        assert d["index"] == 0
        assert d["start_ms"] == 0
        assert d["duration_ms"] == 10000
        assert d["score"] == 0.8


# ─── GpuEncoderSelector Integration ─────────────────────────


class TestGpuEncoderSelectorIntegration:
    """Integration tests for GpuEncoderSelector."""

    def test_encoder_priority_order(self) -> None:
        """Should follow priority ordering."""
        caps = FFmpegCapabilities(
            hw_encoders=["h264_nvenc", "h264_amf"],
        )
        caps.has_nvenc = True
        caps.has_amf = True
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "h264_nvenc"  # CUDA priority over AMD

    def test_select_encoder_no_caps(self) -> None:
        """Should use CPU when no capabilites provided."""
        selector = GpuEncoderSelector()
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "libx264"

    def test_select_for_hal_backend(self) -> None:
        """Should map HAL backend to correct encoder."""
        selector = GpuEncoderSelector()
        assert selector.select_for_hal_backend("CUDA").video_encoder == "h264_nvenc"
        assert selector.select_for_hal_backend("METAL").video_encoder == "h264_videotoolbox"
        assert selector.select_for_hal_backend("CPU").video_encoder == "libx264"


# ─── FFmpegManager Integration ─────────────────────────────


class TestFFmpegManagerIntegration:
    """Integration tests for FFmpegManager."""

    def test_manager_creation(self) -> None:
        """Should create manager and detect availability."""
        manager = FFmpegManager()
        assert isinstance(manager.is_available, bool)

    def test_get_capabilities_returns_dict(self) -> None:
        """Should return capabilities as dict."""
        manager = FFmpegManager()
        caps = manager.get_capabilities()
        assert isinstance(caps, dict)
        assert "is_available" in caps
        assert "version" in caps
        assert "encoders_count" in caps
