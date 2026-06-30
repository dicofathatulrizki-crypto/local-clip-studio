"""Unit tests for GpuEncoderSelector and ExportEncoder."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.infrastructure.ffmpeg.export import (
    EncoderMapping,
    ExportEncoder,
    ExportResult,
    GpuEncoderSelector,
)
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities
from backend.infrastructure.ffmpeg.types import ExportParams


class TestGpuEncoderSelector:
    """Tests for GPU-aware encoder selection."""

    def test_select_encoder_cpu_default(self) -> None:
        """Should default to CPU encoder when no capabilities."""
        selector = GpuEncoderSelector()
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "libx264"

    def test_select_encoder_nvenc(self) -> None:
        """Should select NVENC when available."""
        caps = FFmpegCapabilities(hw_encoders=["h264_nvenc"], encoders=["h264_nvenc", "libx264"])
        # Mark nvenc detection through hw_encoders
        caps.has_nvenc = True
        caps.has_cuda = True
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "h264_nvenc"

    def test_select_encoder_amf(self) -> None:
        """Should select AMF when NVENC unavailable but AMF available."""
        caps = FFmpegCapabilities(hw_encoders=["h264_amf"])
        caps.has_amf = True
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "h264_amf"

    def test_select_encoder_videotoolbox(self) -> None:
        """Should select VideoToolbox when other GPU unavailable."""
        caps = FFmpegCapabilities(hw_encoders=["h264_videotoolbox"])
        caps.has_videotoolbox = True
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "h264_videotoolbox"

    def test_select_encoder_vaapi(self) -> None:
        """Should select VAAPI when only VAAPI available."""
        caps = FFmpegCapabilities(hw_encoders=["h264_vaapi"])
        caps.has_vaapi = True
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "h264_vaapi"

    def test_select_encoder_fallback_to_cpu(self) -> None:
        """Should fall back to CPU when no GPU encoders."""
        caps = FFmpegCapabilities(encoders=["libx264"])
        selector = GpuEncoderSelector(capabilities=caps)
        mapping = selector.select_encoder()
        assert mapping.video_encoder == "libx264"

    def test_select_encoder_prefer_hevc(self) -> None:
        """Should prefer HEVC when requested."""
        selector = GpuEncoderSelector()
        mapping = selector.select_encoder(prefer_hevc=True)
        assert mapping.video_encoder == "libx265"

    def test_select_encoder_specific_backend(self) -> None:
        """Should select encoder for specific backend type."""
        selector = GpuEncoderSelector()
        mapping = selector.select_encoder(backend_type="metal")
        assert mapping.video_encoder == "h264_videotoolbox"

    def test_select_encoder_unknown_backend(self) -> None:
        """Should fall back to CPU for unknown backend type."""
        selector = GpuEncoderSelector()
        mapping = selector.select_encoder(backend_type="unknown")
        assert mapping.video_encoder == "libx264"

    def test_select_for_hal_backend_cuda(self) -> None:
        """Should map HAL backend name to encoder."""
        selector = GpuEncoderSelector()
        mapping = selector.select_for_hal_backend("CUDA")
        assert mapping.video_encoder == "h264_nvenc"

    def test_select_for_hal_backend_metal(self) -> None:
        """Should map MPS backend to VideoToolbox."""
        selector = GpuEncoderSelector()
        mapping = selector.select_for_hal_backend("MPS")
        assert mapping.video_encoder == "h264_videotoolbox"

    def test_select_for_hal_backend_unknown(self) -> None:
        """Should fall back to CPU for unknown HAL backend."""
        selector = GpuEncoderSelector()
        mapping = selector.select_for_hal_backend("unknown")
        assert mapping.video_encoder == "libx264"

    def test_encoder_is_available(self) -> None:
        """Should check encoder availability in capabilities."""
        caps = FFmpegCapabilities(encoders=["libx264", "h264_nvenc"])
        selector = GpuEncoderSelector()
        assert selector.encoder_is_available("libx264", caps)
        assert selector.encoder_is_available("h264_nvenc", caps)
        assert not selector.encoder_is_available("nonexistent", caps)

    def test_get_supported_encoders(self) -> None:
        """Should return list of supported encoder options."""
        selector = GpuEncoderSelector()
        encoders = selector.get_supported_encoders()
        assert len(encoders) > 0
        names = [e["name"] for e in encoders]
        assert "libx264" in names
        assert "h264_nvenc" in names

    def test_encoder_mapping_defaults(self) -> None:
        """EncoderMapping should have correct defaults."""
        mapping = EncoderMapping(video_encoder="libx264", hevc_encoder="libx265")
        assert mapping.gpu_params == []
        assert mapping.pixel_format == "yuv420p"
        assert not mapping.supports_high_bit_depth


class TestExportEncoder:
    """Tests for ExportEncoder."""

    @pytest.mark.asyncio
    async def test_encode_with_cpu_default(self) -> None:
        """Should encode with default CPU encoder."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.run.return_value = MagicMock(
            success=True, duration_seconds=5.0, exit_code=0,
            stdout="", stderr="", command="ffmpeg -i in out",
        )

        encoder = ExportEncoder(process_runner=mock_runner)
        result = await encoder.encode("input.mp4", "output.mp4")

        assert result.encoder == "libx264"
        assert result.success
        assert result.preset == "medium"

    @pytest.mark.asyncio
    async def test_encode_with_gpu_backend(self) -> None:
        """Should encode with specified GPU backend."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.run.return_value = MagicMock(
            success=True, duration_seconds=3.0, exit_code=0,
            stdout="", stderr="", command="ffmpeg -i in out",
        )

        caps = FFmpegCapabilities(hw_encoders=["h264_nvenc"])
        caps.has_nvenc = True
        caps.has_cuda = True

        selector = GpuEncoderSelector(capabilities=caps)
        encoder = ExportEncoder(process_runner=mock_runner, encoder_selector=selector)

        result = await encoder.encode("input.mp4", "output.mp4", backend_type="cuda")
        assert result.encoder == "h264_nvenc"
        assert result.success

    @pytest.mark.asyncio
    async def test_encode_with_custom_params(self) -> None:
        """Should accept custom export parameters."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.run.return_value = MagicMock(
            success=True, duration_seconds=10.0, exit_code=0,
            stdout="", stderr="", command="ffmpeg -i in out",
        )

        params = ExportParams(
            video_encoder="libx264",
            preset="slow",
            bitrate="5M",
            crf=18,
        )
        encoder = ExportEncoder(process_runner=mock_runner)
        result = await encoder.encode(
            "input.mp4", "output.mp4",
            params=params,
            prefer_hevc=False,
        )

        assert result.preset == "slow"
        assert result.success

    @pytest.mark.asyncio
    async def test_encode_failure_raises(self) -> None:
        """Should raise on encoding failure."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner.run.side_effect = Exception("Encoding failed")

        encoder = ExportEncoder(process_runner=mock_runner)
        with pytest.raises(Exception, match="Encoding failed"):
            await encoder.encode("input.mp4", "output.mp4")

    def test_export_result_to_dict(self) -> None:
        """Should serialize export result to dict."""
        result = ExportResult(
            path="/out/file.mp4",
            encoder="h264_nvenc",
            preset="fast",
            size_bytes=1024000,
            duration_seconds=5.5,
            success=True,
        )
        d = result.to_dict()
        assert d["path"] == "/out/file.mp4"
        assert d["encoder"] == "h264_nvenc"
        assert d["size_bytes"] == 1024000
        assert d["success"]
