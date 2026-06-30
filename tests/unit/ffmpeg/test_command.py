"""Unit tests for CommandBuilder."""
from __future__ import annotations

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.types import (
    AudioParams,
    CropParams,
    ExportParams,
    FrameExtractParams,
    ProxyParams,
    ThumbnailParams,
    VideoFilters,
)


class TestCommandBuilder:
    """Tests for FFmpeg command construction."""

    def test_probe(self) -> None:
        """Should build ffprobe command."""
        cmd = CommandBuilder.probe("input.mp4")
        assert "-v" in cmd
        assert "quiet" in cmd
        assert "json" in cmd
        assert "-show_format" in cmd
        assert "-show_streams" in cmd
        assert "input.mp4" in cmd

    def test_extract_audio_default(self) -> None:
        """Should build default audio extraction command."""
        cmd = CommandBuilder.extract_audio("input.mp4", "output.wav")
        assert "-i" in cmd
        assert "input.mp4" in cmd
        assert "-vn" in cmd
        assert "-acodec" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "output.wav" in cmd

    def test_extract_audio_with_params(self) -> None:
        """Should build audio extraction command with custom params."""
        params = AudioParams(codec="libmp3lame", sample_rate=44100, channels=2, bitrate="192k")
        cmd = CommandBuilder.extract_audio("input.mp4", "output.mp3", params)
        assert "libmp3lame" in cmd
        assert "44100" in cmd
        assert "2" in cmd
        assert "-b:a" in cmd
        assert "192k" in cmd

    def test_extract_frames_default(self) -> None:
        """Should build default frame extraction command."""
        cmd = CommandBuilder.extract_frames("input.mp4", "frame_%05d.jpg")
        assert "fps=1.0" in " ".join(cmd)
        assert "-qscale:v" in cmd
        assert "frame_%05d.jpg" in cmd

    def test_extract_frames_with_params(self) -> None:
        """Should build frame extraction with custom params."""
        params = FrameExtractParams(fps=0.5, quality=3, max_count=10)
        cmd = CommandBuilder.extract_frames("input.mp4", "frame_%05d.jpg", params)
        full = " ".join(cmd)
        assert "fps=0.5" in full
        assert "-qscale:v" in cmd
        assert "-vframes" in cmd
        assert "10" in cmd

    def test_thumbnail_default(self) -> None:
        """Should build default thumbnail command."""
        cmd = CommandBuilder.thumbnail("input.mp4", "thumb.jpg")
        assert "-ss" in cmd
        assert "1" in cmd
        assert "scale=1280:720" in " ".join(cmd)
        assert "-vframes" in cmd
        assert "1" in cmd
        assert "-y" in cmd

    def test_thumbnail_with_params(self) -> None:
        """Should build thumbnail command with custom params."""
        params = ThumbnailParams(time_seconds=10.5, width=640, height=360, quality=5, pad=False)
        cmd = CommandBuilder.thumbnail("input.mp4", "thumb.jpg", params)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "10.5" in cmd
        assert "scale=640:360" in full
        assert "pad" not in full
        assert "-qscale:v" in cmd
        assert "5" in cmd

    def test_proxy_default(self) -> None:
        """Should build default proxy generation command."""
        cmd = CommandBuilder.proxy("input.mp4", "proxy.mp4")
        full = " ".join(cmd)
        assert "scale=1280:720" in full
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-crf" in cmd
        assert "23" in cmd
        assert "-preset" in cmd
        assert "fast" in cmd
        assert "-an" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_proxy_with_params(self) -> None:
        """Should build proxy command with custom params."""
        params = ProxyParams(width=1920, height=1080, encoder="h264_nvenc", crf=18, preset="slow", pad=True)
        cmd = CommandBuilder.proxy("input.mp4", "proxy.mp4", params)
        full = " ".join(cmd)
        assert "scale=1920:1080" in full
        assert "pad=1920:1080" in full
        assert "h264_nvenc" in cmd
        assert "18" in cmd
        assert "slow" in cmd

    def test_trim_copy(self) -> None:
        """Should build trim command with stream copy."""
        cmd = CommandBuilder.trim("input.mp4", "output.mp4", 10000, 20000, copy=True)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "10.000" in full
        assert "-c" in cmd
        assert "copy" in cmd
        assert "-t" in cmd
        assert "10.000" in full

    def test_trim_reencode(self) -> None:
        """Should build trim command with re-encode."""
        cmd = CommandBuilder.trim("input.mp4", "output.mp4", 5000, 15000, copy=False)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd

    def test_concat(self) -> None:
        """Should build concatenation command."""
        cmd = CommandBuilder.concat("files.txt", "output.mp4")
        assert "-f" in cmd
        assert "concat" in cmd
        assert "-safe" in cmd
        assert "0" in cmd
        assert "-c" in cmd
        assert "copy" in cmd
        assert "-y" in cmd

    def test_normalize_audio(self) -> None:
        """Should build audio normalization command."""
        cmd = CommandBuilder.normalize_audio("input.mp4", "output.mp4")
        full = " ".join(cmd)
        assert "loudnorm" in full
        assert "I=-14.0" in full
        assert "-c:v" in cmd
        assert "copy" in cmd

    def test_waveform(self) -> None:
        """Should build waveform generation command."""
        cmd = CommandBuilder.waveform("input.mp4", "waveform.png", 800, 300)
        full = " ".join(cmd)
        assert "showwavespic" in full
        assert "800x300" in full
        assert "waveform.png" in cmd

    def test_smart_scale(self) -> None:
        """Should build smart scale command."""
        cmd = CommandBuilder.smart_scale("input.mp4", "output.mp4", 640, 360)
        full = " ".join(cmd)
        assert "scale=640:360" in full
        assert "pad=640:360" in full
        assert "-c:v" in cmd
        assert "libx264" in cmd

    def test_crop(self) -> None:
        """Should build crop command."""
        params = CropParams(width=640, height=480, x=100, y=50)
        cmd = CommandBuilder.crop("input.mp4", "output.mp4", params)
        full = " ".join(cmd)
        assert "crop=640:480:100:50" in full

    def test_convert_fps(self) -> None:
        """Should build FPS conversion command."""
        cmd = CommandBuilder.convert_fps("input.mp4", "output.mp4", 29.97)
        full = " ".join(cmd)
        assert "fps=29.97" in full

    def test_calculate_bitrate(self) -> None:
        """Should calculate recommended bitrate."""
        bitrate = CommandBuilder.calculate_bitrate((1920, 1080), 30)
        assert bitrate > 0
        # 1920 * 1080 = 2,073,600 pixels * 0.08 base * 1.0 fps factor
        assert bitrate == 165888

    def test_calculate_bitrate_high_quality(self) -> None:
        """Should calculate higher bitrate for high quality."""
        standard = CommandBuilder.calculate_bitrate((1920, 1080), 30, "standard")
        high = CommandBuilder.calculate_bitrate((1920, 1080), 30, "high")
        assert high > standard

    def test_export_default(self) -> None:
        """Should build default export encoding command."""
        params = ExportParams()
        cmd = CommandBuilder.export("input.mp4", "output.mp4", params)
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd
        assert "medium" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_export_with_gpu_params(self) -> None:
        """Should build export command with GPU acceleration params."""
        params = ExportParams(
            video_encoder="h264_nvenc",
            bitrate="10M",
            crf=None,
            gpu_params=["-hwaccel", "cuda"],
        )
        cmd = CommandBuilder.export("input.mp4", "output.mp4", params)
        assert "h264_nvenc" in cmd
        assert "-b:v" in cmd
        assert "10M" in cmd
        assert "-hwaccel" in cmd
        assert "cuda" in cmd

    def test_build_filter_graph(self) -> None:
        """Should build filter graph string from VideoFilters."""
        filters = VideoFilters(
            scale=(1920, 1080),
            fps=30.0,
            flip_h=True,
        )
        result = CommandBuilder.build_filter_graph(filters)
        assert "scale=1920:1080" in result
        assert "fps=30.0" in result
        assert "hflip" in result

    def test_build_filter_graph_with_crop(self) -> None:
        """Should build filter graph with crop."""
        filters = VideoFilters(
            crop=CropParams(width=640, height=480, x=10, y=20),
            rotate=90.0,
        )
        result = CommandBuilder.build_filter_graph(filters)
        assert "crop=640:480:10:20" in result
        assert "rotate=90.0*PI/180" in result
