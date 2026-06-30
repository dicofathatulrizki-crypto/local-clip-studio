"""Unit tests for ProgressParser."""
from __future__ import annotations

import pytest

from backend.infrastructure.ffmpeg.progress import MediaProgress, ProgressParser


class TestMediaProgress:
    """Tests for MediaProgress dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        p = MediaProgress()
        assert p.frame == 0
        assert p.fps == 0.0
        assert p.time_ms == 0
        assert p.speed == 0.0
        assert p.progress == 0.0

    def test_percent_calculation(self) -> None:
        """Should calculate percentage from progress."""
        p = MediaProgress(progress=0.5)
        assert p.percent == 50.0

    def test_time_formatted_zero(self) -> None:
        """Should format zero time."""
        p = MediaProgress(time_ms=0)
        assert p.time_formatted == "0:00"

    def test_time_formatted_with_hours(self) -> None:
        """Should format time with hours."""
        p = MediaProgress(time_ms=3661000)  # 1h 1m 1s
        assert p.time_formatted == "1:01:01"

    def test_time_formatted_minutes(self) -> None:
        """Should format time without hours."""
        p = MediaProgress(time_ms=125000)  # 2m 5s
        assert p.time_formatted == "2:05"

    def test_to_dict(self) -> None:
        """Should serialize to dict."""
        p = MediaProgress(frame=100, fps=30.0, time_ms=5000, speed=1.5, progress=0.25)
        d = p.to_dict()
        assert d["frame"] == 100
        assert d["fps"] == 30.0
        assert d["time_ms"] == 5000
        assert d["speed"] == 1.5
        assert d["progress"] == 0.25
        assert d["percent"] == 25.0


class TestProgressParser:
    """Tests for ProgressParser."""

    def test_init(self) -> None:
        """Should initialize with duration and callback."""
        parser = ProgressParser(total_duration_ms=60000)
        assert parser._total == 60000
        assert parser._callback is None

    def test_parse_frame_line(self) -> None:
        """Should parse frame count from stderr line."""
        parser = ProgressParser()
        p = parser.parse_line("frame=  120 fps=30.0")
        assert p.frame == 120
        assert p.fps == 30.0

    def test_parse_time_line(self) -> None:
        """Should parse time from stderr line."""
        parser = ProgressParser(total_duration_ms=120000)
        p = parser.parse_line("time=00:01:30.00 bitrate=1500.0kb/s")
        assert p.time_ms == 90000
        assert p.bitrate_kbps == 1500.0
        assert p.progress == 0.75

    def test_parse_speed_line(self) -> None:
        """Should parse speed from stderr line."""
        parser = ProgressParser()
        p = parser.parse_line("speed=2.5x")
        assert p.speed == 2.5

    def test_parse_key_value_format(self) -> None:
        """Should parse -progress flag key=value format."""
        parser = ProgressParser(total_duration_ms=60000)
        p = parser.parse_line("out_time_ms=30000000")
        assert p.time_ms == 30000  # Divided by 1000 in parser

        p = parser.parse_line("frame=500")
        assert p.frame == 500

    def test_parse_size_line(self) -> None:
        """Should parse output size from stderr."""
        parser = ProgressParser()
        p = parser.parse_line("size=    5120kB")
        assert p.size_kb == 5120

    def test_parse_quality_line(self) -> None:
        """Should parse quality from stderr."""
        parser = ProgressParser()
        p = parser.parse_line("q=23.0")
        assert p.quality == 23.0

    def test_parse_lines_batch(self) -> None:
        """Should parse multiple lines and return final state."""
        parser = ProgressParser(total_duration_ms=120000)
        lines = [
            "frame=   10 fps=15.0",
            "frame=   20 fps=20.0 q=23.0",
            "time=00:00:05.00 bitrate=500.0kb/s speed=1.5x",
            "time=00:00:10.00 bitrate=600.0kb/s speed=1.8x",
        ]
        final = parser.parse_lines(lines)
        assert final.frame == 20
        assert final.time_ms == 10000
        assert final.speed == 1.8
        assert final.bitrate_kbps == 600.0

    def test_callback_is_called(self) -> None:
        """Should call progress callback on each line."""
        calls: list[float] = []

        def callback(p: MediaProgress) -> None:
            calls.append(p.progress)

        parser = ProgressParser(total_duration_ms=100000, callback=callback)
        parser.parse_line("time=00:00:10.00")
        parser.parse_line("time=00:00:50.00")

        assert len(calls) == 2
        assert calls[0] == 0.1
        assert calls[1] == 0.5

    def test_set_duration(self) -> None:
        """Should update total duration after init."""
        parser = ProgressParser(total_duration_ms=60000)
        parser.set_duration(120000)
        assert parser._total == 120000

        p = parser.parse_line("time=00:01:00.00")
        assert p.progress == 0.5

    def test_current_property(self) -> None:
        """Should return current progress state."""
        parser = ProgressParser()
        assert parser.current.frame == 0

        parser.parse_line("frame=50")
        assert parser.current.frame == 50

    def test_reset(self) -> None:
        """Should reset parser to initial state."""
        parser = ProgressParser(total_duration_ms=60000)
        parser.parse_line("frame=100 time=00:00:30.00")
        assert parser.current.frame == 100

        parser.reset()
        assert parser.current.frame == 0
        assert parser.current.time_ms == 0
