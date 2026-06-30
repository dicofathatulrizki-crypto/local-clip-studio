"""Unit tests for FFmpegManager."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.ffmpeg.manager import FFmpegManager


class TestFFmpegManager:
    """Tests for the top-level FFmpeg orchestrator."""

    def test_init_defaults(self) -> None:
        """Should initialize with default components."""
        manager = FFmpegManager()
        assert not manager.is_available  # FFmpeg not installed in test env

    def test_is_available(self) -> None:
        """Should reflect FFmpeg availability."""
        locator = MagicMock()
        locator.is_available.return_value = False
        manager = FFmpegManager(locator=locator)
        assert not manager.is_available

        locator.is_available.return_value = True
        assert manager.is_available

    def test_capabilities(self) -> None:
        """Should return detected capabilities."""
        locator = MagicMock()
        caps = MagicMock()
        caps.version_str = "6.1.1"
        locator.detect_capabilities.return_value = caps
        manager = FFmpegManager(locator=locator)
        assert manager.capabilities.version_str == "6.1.1"

    def test_ffmpeg_path(self) -> None:
        """Should return FFmpeg binary path."""
        locator = MagicMock()
        locator.ffmpeg_path = "/usr/bin/ffmpeg"
        manager = FFmpegManager(locator=locator)
        assert manager.ffmpeg_path == "/usr/bin/ffmpeg"

    def test_ffprobe_path(self) -> None:
        """Should return FFprobe binary path."""
        locator = MagicMock()
        locator.ffprobe_path = "/usr/bin/ffprobe"
        manager = FFmpegManager(locator=locator)
        assert manager.ffprobe_path == "/usr/bin/ffprobe"

    @pytest.mark.asyncio
    async def test_probe(self) -> None:
        """Should probe media file for metadata."""
        probe_service = MagicMock()
        info = MagicMock()
        info.duration_ms = 60000
        probe_service.probe.return_value = info

        manager = FFmpegManager(probe_service=probe_service)
        result = await manager.probe("input.mp4")

        assert result.duration_ms == 60000
        probe_service.probe.assert_called_once_with("input.mp4")

    def test_probe_sync(self) -> None:
        """Should probe synchronously."""
        probe_service = MagicMock()
        info = MagicMock()
        info.duration_ms = 30000
        probe_service.probe.return_value = info

        manager = FFmpegManager(probe_service=probe_service)
        result = manager.probe_sync("input.mp4")

        assert result.duration_ms == 30000

    @pytest.mark.asyncio
    async def test_get_video_info(self) -> None:
        """Should return video info as dict."""
        video_info = MagicMock()
        video_info.to_dict.return_value = {"width": 1920, "height": 1080}

        manager = FFmpegManager(video_info=video_info)
        result = await manager.get_video_info("input.mp4")

        assert result["width"] == 1920
        assert result["height"] == 1080

    @pytest.mark.asyncio
    async def test_generate_thumbnail(self) -> None:
        """Should generate thumbnail with default params."""
        thumbnail = MagicMock()
        thumbnail.generate = AsyncMock()
        result = MagicMock()
        result.path = "/tmp/thumb.jpg"
        result.success = True
        thumbnail.generate.return_value = result

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, thumbnail=thumbnail)
        result2 = await manager.generate_thumbnail("input.mp4", "thumb.jpg")

        assert result2.path == "/tmp/thumb.jpg"
        assert result2.success

    @pytest.mark.asyncio
    async def test_generate_proxy(self) -> None:
        """Should generate proxy video."""
        proxy = MagicMock()
        proxy.generate = AsyncMock()
        result = MagicMock()
        result.path = "/tmp/proxy.mp4"
        result.success = True
        proxy.generate.return_value = result

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, proxy=proxy)
        result2 = await manager.generate_proxy("input.mp4", "proxy.mp4")

        assert result2.success

    @pytest.mark.asyncio
    async def test_extract_audio(self) -> None:
        """Should extract audio from video."""
        audio = MagicMock()
        audio.extract = AsyncMock()
        result = MagicMock()
        result.path = "/tmp/audio.wav"
        result.success = True
        audio.extract.return_value = result

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, audio=audio)
        result2 = await manager.extract_audio("input.mp4", "audio.wav")

        assert result2.success

    @pytest.mark.asyncio
    async def test_extract_frames(self) -> None:
        """Should extract frames from video."""
        frame = MagicMock()
        frame.extract = AsyncMock()
        frame.extract.return_value = []

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, frame=frame)
        results = await manager.extract_frames("input.mp4", "/tmp/frames/")

        assert results == []

    @pytest.mark.asyncio
    async def test_detect_scenes(self) -> None:
        """Should detect scene changes."""
        scene = MagicMock()
        scene.detect_scenes = AsyncMock()
        scene.detect_scenes.return_value = []

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, scene=scene)
        scenes = await manager.detect_scenes("input.mp4")

        assert scenes == []

    @pytest.mark.asyncio
    async def test_export_encode(self) -> None:
        """Should export encode with default params."""
        export = MagicMock()
        export.encode = AsyncMock()
        result = MagicMock()
        result.path = "/tmp/output.mp4"
        result.success = True
        export.encode.return_value = result

        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        manager = FFmpegManager(locator=locator, export_encoder=export)
        result2 = await manager.export_encode("input.mp4", "output.mp4")

        assert result2.success

    @pytest.mark.asyncio
    async def test_trim(self) -> None:
        """Should trim video segment."""
        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        runner = MagicMock()
        runner.run = AsyncMock()
        runner_result = MagicMock()
        runner_result.success = True
        runner.run.return_value = runner_result

        manager = FFmpegManager(locator=locator, process_runner=runner)
        result = await manager.trim("input.mp4", "output.mp4", 10000, 20000)

        assert result.success

    @pytest.mark.asyncio
    async def test_concat(self) -> None:
        """Should concatenate videos."""
        locator = MagicMock()
        locator.ffmpeg_path = "ffmpeg"

        runner = MagicMock()
        runner.run = AsyncMock()
        runner_result = MagicMock()
        runner_result.success = True
        runner.run.return_value = runner_result

        manager = FFmpegManager(locator=locator, process_runner=runner)
        result = await manager.concat("files.txt", "output.mp4")

        assert result.success

    def test_check_encoder(self) -> None:
        """Should check encoder availability."""
        locator = MagicMock()
        locator.check_encoder.return_value = True
        manager = FFmpegManager(locator=locator)
        assert manager.check_encoder("libx264")
        locator.check_encoder.assert_called_with("libx264")

    def test_get_encoder_list(self) -> None:
        """Should return list of available encoders."""
        locator = MagicMock()
        locator.get_encoder_list.return_value = ["libx264", "aac"]
        manager = FFmpegManager(locator=locator)
        encoders = manager.get_encoder_list()
        assert len(encoders) == 2

    def test_get_capabilities(self) -> None:
        """Should return capabilities dict."""
        locator = MagicMock()
        caps = MagicMock()
        caps.is_installed = True
        caps.version_str = "6.1.1"
        caps.version_tuple = (6, 1, 1)
        caps.encoders = ["libx264"]
        caps.decoders = ["h264"]
        caps.hw_encoders = []
        caps.has_nvenc = False
        caps.has_amf = False
        caps.has_videotoolbox = False
        caps.has_vaapi = False
        locator.detect_capabilities.return_value = caps

        manager = FFmpegManager(locator=locator)
        result = manager.get_capabilities()
        assert result["is_available"]
        assert result["version"] == "6.1.1"
