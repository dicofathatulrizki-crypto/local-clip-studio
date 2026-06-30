"""FFmpegLocator — discovers FFmpeg and FFprobe binaries, checks version, detects capabilities.

Supports:
- System-installed FFmpeg (via PATH)
- Custom binary path
- Version verification (minimum 6.0)
- Encoder/decoder detection
- Hardware encoder detection (NVENC, AMF, VideoToolbox, VAAPI)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FFmpegCapabilities:
    """Detected FFmpeg capabilities."""
    version: str = ""
    version_tuple: tuple[int, int, int] = (0, 0, 0)
    encoders: list[str] = field(default_factory=list)
    decoders: list[str] = field(default_factory=list)
    hw_accels: list[str] = field(default_factory=list)
    hw_encoders: list[str] = field(default_factory=list)
    hw_decoders: list[str] = field(default_factory=list)
    has_nvenc: bool = False
    has_amf: bool = False
    has_videotoolbox: bool = False
    has_vaapi: bool = False
    has_qsv: bool = False
    has_cuda: bool = False
    formats: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)

    @property
    def is_installed(self) -> bool:
        return self.version_tuple >= (6, 0, 0)

    @property
    def version_str(self) -> str:
        return self.version


class FFmpegLocator:
    """Locates FFmpeg and FFprobe binaries and reports capabilities.

    Usage:
        locator = FFmpegLocator()
        caps = locator.detect_capabilities()
        if caps.is_installed:
            ffmpeg_path = locator.ffmpeg_path
    """

    MINIMUM_VERSION = (6, 0, 0)

    def __init__(
        self,
        ffmpeg_path: str | Path | None = None,
        ffprobe_path: str | Path | None = None,
    ) -> None:
        self._ffmpeg_path: str | None = None
        self._ffprobe_path: str | None = None
        self._capabilities: FFmpegCapabilities | None = None

        if ffmpeg_path:
            self._ffmpeg_path = str(ffmpeg_path)
        if ffprobe_path:
            self._ffprobe_path = str(ffprobe_path)

    @property
    def ffmpeg_path(self) -> str:
        """Get the FFmpeg binary path.

        Raises:
            FFmpegNotInstalledError: If FFmpeg is not found.
        """
        if self._ffmpeg_path is None:
            self._ffmpeg_path = self._find_ffmpeg()
        return self._ffmpeg_path

    @property
    def ffprobe_path(self) -> str:
        """Get the FFprobe binary path.

        Raises:
            FFmpegNotInstalledError: If FFprobe is not found.
        """
        if self._ffprobe_path is None:
            self._ffprobe_path = self._find_ffprobe()
        return self._ffprobe_path

    def is_available(self) -> bool:
        """Check if FFmpeg is installed and meets minimum version."""
        try:
            caps = self.detect_capabilities()
            return caps.is_installed
        except Exception:
            return False

    def detect_capabilities(self) -> FFmpegCapabilities:
        """Run full capability detection.

        Returns:
            FFmpegCapabilities with all detected features.

        Raises:
            FFmpegNotInstalledError: If FFmpeg is not found.
        """
        if self._capabilities is not None:
            return self._capabilities

        caps = FFmpegCapabilities()

        # Version
        try:
            result = self._run_ffmpeg(["-version"])
            caps.version = self._parse_version_line(result)
            caps.version_tuple = self._parse_version_tuple(caps.version)
        except Exception:
            pass

        if not caps.is_installed:
            return caps

        # Encoders
        try:
            result = self._run_ffmpeg(["-encoders"])
            for line in result.split("\n"):
                if line.startswith(" "):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        codec = parts[1]
                        caps.encoders.append(codec)
                        # Detect hardware encoders
                        if "nvenc" in codec:
                            caps.hw_encoders.append(codec)
                            caps.has_nvenc = True
                        elif "amf" in codec:
                            caps.hw_encoders.append(codec)
                            caps.has_amf = True
                        elif "videotoolbox" in codec:
                            caps.hw_encoders.append(codec)
                            caps.has_videotoolbox = True
                        elif "vaapi" in codec:
                            caps.hw_encoders.append(codec)
                            caps.has_vaapi = True
                        elif "qsv" in codec:
                            caps.hw_encoders.append(codec)
                            caps.has_qsv = True
        except Exception:
            pass

        # Decoders
        try:
            result = self._run_ffmpeg(["-decoders"])
            for line in result.split("\n"):
                if line.startswith(" "):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        codec = parts[1]
                        caps.decoders.append(codec)
                        if "cuvid" in codec or "nvenc" in codec:
                            caps.has_cuda = True
        except Exception:
            pass

        # HW accelerators
        try:
            result = self._run_ffmpeg(["-hwaccels"])
            for line in result.split("\n"):
                line = line.strip()
                if line and not line.startswith("Hardware"):
                    caps.hw_accels.append(line)
        except Exception:
            pass

        # Formats
        try:
            result = self._run_ffmpeg(["-formats"])
            for line in result.split("\n"):
                if len(line) > 5 and (line[2] == "E" or line[2] == "D"):
                    fmt = line.split()[-1]
                    caps.formats.append(fmt)
        except Exception:
            pass

        # Filters
        try:
            result = self._run_ffmpeg(["-filters"])
            for line in result.split("\n"):
                if line.strip() and " " in line:
                    parts = line.strip().split()
                    if parts and not parts[0].startswith("."):
                        caps.filters.append(parts[0])
        except Exception:
            pass

        self._capabilities = caps
        return caps

    def check_encoder(self, encoder_name: str) -> bool:
        """Check if a specific encoder is available.

        Args:
            encoder_name: Encoder name (e.g., 'h264_nvenc', 'libx264').

        Returns:
            True if the encoder is available.
        """
        caps = self.detect_capabilities()
        return encoder_name in caps.encoders

    def check_filter(self, filter_name: str) -> bool:
        """Check if a specific filter is available.

        Args:
            filter_name: Filter name (e.g., 'scale', 'crop').

        Returns:
            True if the filter is available.
        """
        caps = self.detect_capabilities()
        return filter_name in caps.filters

    def get_encoder_list(self) -> list[str]:
        """Get list of all available encoders.

        Returns:
            List of encoder names.
        """
        return self.detect_capabilities().encoders

    # ─── Private ────────────────────────────────────────────────

    def _find_ffmpeg(self) -> str:
        """Find FFmpeg binary on the system."""
        path = shutil.which("ffmpeg")
        if path:
            return path
        # Check common locations
        common_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
            str(Path.home() / "bin" / "ffmpeg"),
        ]
        for p in common_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        from backend.infrastructure.ffmpeg.errors import FFmpegNotInstalledError
        raise FFmpegNotInstalledError()

    def _find_ffprobe(self) -> str:
        """Find FFprobe binary on the system."""
        path = shutil.which("ffprobe")
        if path:
            return path
        common_paths = [
            "/usr/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/opt/homebrew/bin/ffprobe",
            str(Path.home() / "bin" / "ffprobe"),
        ]
        for p in common_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        from backend.infrastructure.ffmpeg.errors import FFmpegNotInstalledError
        raise FFmpegNotInstalledError("FFprobe not found. Install FFmpeg 6.0+.")

    def _run_ffmpeg(self, args: list[str]) -> str:
        """Run FFmpeg with given args and return stdout."""
        # Use the configured path first, then fall back to system PATH
        ffmpeg = self._ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
        result = subprocess.run(
            [ffmpeg] + args,
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout + "\n" + result.stderr

    @staticmethod
    def _parse_version_line(output: str) -> str:
        """Extract version string from FFmpeg version output."""
        for line in output.split("\n"):
            if "ffmpeg version" in line.lower():
                return line.strip()
        return "unknown"

    @staticmethod
    def _parse_version_tuple(version_str: str) -> tuple[int, int, int]:
        """Parse version string into a tuple for comparison."""
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version_str)
        if match:
            groups = match.groups()
            return (
                int(groups[0]),
                int(groups[1]),
                int(groups[2]) if groups[2] else 0,
            )
        return (0, 0, 0)
