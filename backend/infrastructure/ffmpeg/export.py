"""ExportEncoder — GPU-accelerated export encoding with automatic hardware selection.

Integrates with the HAL (Module A6) to select the optimal encoder based on
available hardware. Falls back gracefully when hardware encoding is unavailable.

Encoder mapping:
- CUDA    → h264_nvenc / hevc_nvenc
- ROCm    → h264_amf / hevc_amf / h264_vaapi
- Metal   → h264_videotoolbox / hevc_videotoolbox
- CPU     → libx264 / libx265
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.errors import FFmpegError
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities
from backend.infrastructure.ffmpeg.process import ProcessRunner
from backend.infrastructure.ffmpeg.types import ExportParams


@dataclass
class EncoderMapping:
    """Maps a HAL backend type to FFmpeg encoder names."""
    video_encoder: str
    hevc_encoder: str
    gpu_params: list[str] = field(default_factory=list)
    pixel_format: str = "yuv420p"
    supports_high_bit_depth: bool = False


class GpuEncoderSelector:
    """Selects the optimal FFmpeg encoder based on available hardware.

    Integrates with Module A6 (HAL) when available, falling back to
    FFmpeg capability detection when HAL is not yet initialized.
    """

    ENCODER_MAP: dict[str, EncoderMapping] = {
        "cuda": EncoderMapping(
            video_encoder="h264_nvenc",
            hevc_encoder="hevc_nvenc",
            gpu_params=["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"],
            pixel_format="yuv420p",
            supports_high_bit_depth=True,
        ),
        "rocm": EncoderMapping(
            video_encoder="h264_amf",
            hevc_encoder="hevc_amf",
            gpu_params=["-hwaccel", "amf"],
            pixel_format="yuv420p",
            supports_high_bit_depth=False,
        ),
        "metal": EncoderMapping(
            video_encoder="h264_videotoolbox",
            hevc_encoder="hevc_videotoolbox",
            gpu_params=[],
            pixel_format="nv12",
            supports_high_bit_depth=True,
        ),
        "vaapi": EncoderMapping(
            video_encoder="h264_vaapi",
            hevc_encoder="hevc_vaapi",
            gpu_params=["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"],
            pixel_format="vaapi",
            supports_high_bit_depth=False,
        ),
        "cpu": EncoderMapping(
            video_encoder="libx264",
            hevc_encoder="libx265",
            gpu_params=[],
            pixel_format="yuv420p",
            supports_high_bit_depth=True,
        ),
    }

    def __init__(self, capabilities: FFmpegCapabilities | None = None) -> None:
        self._caps = capabilities
        self._integrated_hal: bool = False

    def select_encoder(
        self,
        prefer_hevc: bool = False,
        backend_type: str = "auto",
    ) -> EncoderMapping:
        """Select the optimal encoder for the current hardware.

        Priority: CUDA → ROCm → Metal → VAAPI → CPU

        Args:
            prefer_hevc: If True, prefer HEVC over AVC.
            backend_type: 'cuda', 'rocm', 'metal', 'vaapi', 'cpu', or 'auto'.

        Returns:
            EncoderMapping with selected encoder and GPU params.

        Raises:
            FFmpegError: If no encoder is available.
        """
        if self._caps is None:
            # No capability info — default to CPU
            return self._get_encoder("cpu", prefer_hevc)

        if backend_type != "auto":
            # User-specified backend
            key = backend_type.lower()
            if key in self.ENCODER_MAP:
                return self._get_encoder(key, prefer_hevc)
            return self._get_encoder("cpu", prefer_hevc)

        # Auto-detect: priority order
        if self._caps.has_nvenc or self._caps.has_cuda:
            return self._get_encoder("cuda", prefer_hevc)
        if self._caps.has_amf:
            return self._get_encoder("rocm", prefer_hevc)
        if self._caps.has_videotoolbox:
            return self._get_encoder("metal", prefer_hevc)
        if self._caps.has_vaapi:
            return self._get_encoder("vaapi", prefer_hevc)

        return self._get_encoder("cpu", prefer_hevc)

    def select_for_hal_backend(self, backend: str, prefer_hevc: bool = False) -> EncoderMapping:
        """Select encoder based on HAL backend type string.

        Args:
            backend: HAL backend type (e.g., 'CUDA', 'METAL', 'CPU').
            prefer_hevc: If True, prefer HEVC over AVC.

        Returns:
            EncoderMapping with appropriate encoder.
        """
        mapping: dict[str, str] = {
            "cuda": "cuda",
            "rocm": "rocm",
            "metal": "metal",
            "mps": "metal",
            "cpu": "cpu",
        }
        key = mapping.get(backend.lower(), "cpu")
        return self._get_encoder(key, prefer_hevc)

    def encoder_is_available(self, encoder: str, caps: FFmpegCapabilities) -> bool:
        """Check if a specific encoder is available in the detected capabilities.

        Args:
            encoder: Encoder name (e.g., 'h264_nvenc').
            caps: Detected FFmpeg capabilities.

        Returns:
            True if the encoder is in the available encoders list.
        """
        return encoder in caps.encoders

    def get_supported_encoders(self) -> list[dict[str, str]]:
        """Get all supported encoder options for UI display.

        Returns:
            List of dicts with 'name', 'type', and 'description' keys.
        """
        return [
            {"name": "libx264", "type": "cpu", "description": "Software H.264 (widest compatibility)"},
            {"name": "libx265", "type": "cpu", "description": "Software HEVC (better compression)"},
            {"name": "h264_nvenc", "type": "cuda", "description": "NVIDIA NVENC H.264"},
            {"name": "hevc_nvenc", "type": "cuda", "description": "NVIDIA NVENC HEVC"},
            {"name": "h264_amf", "type": "rocm", "description": "AMD AMF H.264"},
            {"name": "hevc_amf", "type": "rocm", "description": "AMD AMF HEVC"},
            {"name": "h264_videotoolbox", "type": "metal", "description": "Apple VideoToolbox H.264"},
            {"name": "hevc_videotoolbox", "type": "metal", "description": "Apple VideoToolbox HEVC"},
            {"name": "h264_vaapi", "type": "vaapi", "description": "VAAPI H.264"},
        ]

    def _get_encoder(self, backend_key: str, prefer_hevc: bool) -> EncoderMapping:
        """Get the encoder mapping for a backend, preferring HEVC if requested."""
        mapping = self.ENCODER_MAP.get(backend_key, self.ENCODER_MAP["cpu"])
        if prefer_hevc:
            # Swap to HEVC encoder
            mapping = EncoderMapping(
                video_encoder=mapping.hevc_encoder,
                hevc_encoder=mapping.hevc_encoder,
                gpu_params=mapping.gpu_params,
                pixel_format=mapping.pixel_format,
                supports_high_bit_depth=mapping.supports_high_bit_depth,
            )
        return mapping


class ExportEncoder:
    """Encodes video exports using the optimal encoder for the hardware.

    Combines command building, GPU-aware encoder selection, and process
    execution into a single export operation.
    """

    def __init__(
        self,
        process_runner: ProcessRunner | None = None,
        command_builder: type[CommandBuilder] | None = None,
        encoder_selector: GpuEncoderSelector | None = None,
    ) -> None:
        self._runner = process_runner or ProcessRunner()
        self._builder = command_builder or CommandBuilder
        self._selector = encoder_selector or GpuEncoderSelector()

    async def encode(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: ExportParams | None = None,
        ffmpeg_path: str = "ffmpeg",
        timeout_seconds: int = 3600,
        prefer_hevc: bool = False,
        backend_type: str = "auto",
        total_duration_ms: int = 0,
    ) -> ExportResult:
        """Encode a video export with automatic hardware acceleration.

        Args:
            input_path: Source video path.
            output_path: Output path.
            params: Export parameters (encoder, bitrate, preset, etc.).
            ffmpeg_path: Path to FFmpeg binary.
            timeout_seconds: Maximum execution time (default: 1 hour).
            prefer_hevc: If True, prefer HEVC over H.264.
            backend_type: Hardware backend ('cuda', 'rocm', 'metal', 'cpu', 'auto').
            total_duration_ms: Total duration for progress tracking.

        Returns:
            ExportResult with output metadata.

        Raises:
            FFmpegError: On encoding failure.
        """
        encoder_mapping = self._selector.select_encoder(
            prefer_hevc=prefer_hevc,
            backend_type=backend_type,
        )

        p = params or ExportParams()
        p.video_encoder = encoder_mapping.video_encoder
        p.pixel_format = encoder_mapping.pixel_format
        p.gpu_params = encoder_mapping.gpu_params

        cmd = self._builder.export(str(input_path), str(output_path), p)

        result = await self._runner.run(
            cmd=cmd,
            ffmpeg_path=ffmpeg_path,
            timeout_seconds=timeout_seconds,
            total_duration_ms=total_duration_ms,
            retry_count=2,
        )

        out_path = Path(output_path)
        return ExportResult(
            path=str(out_path),
            encoder=p.video_encoder,
            preset=p.preset,
            size_bytes=out_path.stat().st_size if out_path.exists() else 0,
            duration_seconds=result.duration_seconds,
            success=result.success,
        )


class ExportResult:
    """Result of an export encoding operation."""

    def __init__(
        self,
        path: str,
        encoder: str,
        preset: str,
        size_bytes: int,
        duration_seconds: float,
        success: bool,
    ) -> None:
        self.path = path
        self.encoder = encoder
        self.preset = preset
        self.size_bytes = size_bytes
        self.duration_seconds = duration_seconds
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "encoder": self.encoder,
            "preset": self.preset,
            "size_bytes": self.size_bytes,
            "duration_seconds": round(self.duration_seconds, 2),
            "success": self.success,
        }
