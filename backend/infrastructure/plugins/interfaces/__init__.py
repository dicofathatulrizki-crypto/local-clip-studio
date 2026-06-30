"""Plugin Provider Interfaces — formal contracts for all AI plugin types.

Every plugin must implement the interface corresponding to its type.
Interfaces are fully typed, documented, versioned, and extensible.

Available interfaces:
    - STTProvider       (speech-to-text)
    - VisionProvider    (vision/detection)
    - LLMProvider       (language model)
    - CaptionProvider   (caption/subtitle generation)
    - TranslationProvider (language translation)
    - ExportProvider    (video/file export)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


# ═══════════════════════════════════════════════════════════
# Common Base Types
# ═══════════════════════════════════════════════════════════

@dataclass
class ProviderResult:
    """Standard result from any provider operation."""
    success: bool = True
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str = ""
    name: str = ""
    size_mb: int = 0
    vram_mb: int = 0
    performance: str = ""  # "low", "medium", "high"
    supported_languages: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# Base Provider
# ═══════════════════════════════════════════════════════════

class BaseProvider(ABC):
    """Base class for all plugin providers.

    Every provider must implement:
    - load()            — load models/resources
    - unload()          — release resources
    - health_check()    — return health status
    """

    PROVIDER_VERSION: str = "1.0.0"

    @abstractmethod
    def load(self, config: dict[str, Any] | None = None) -> ProviderResult:
        """Load the provider's models and resources.

        Args:
            config: Optional configuration dictionary.

        Returns:
            ProviderResult indicating success or failure.
        """
        ...

    @abstractmethod
    def unload(self) -> ProviderResult:
        """Release all resources held by the provider.

        Returns:
            ProviderResult indicating success or failure.
        """
        ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return the current health status of the provider.

        Returns:
            Dict with at least 'status' key ('ok' or 'error').
        """
        ...

    def get_provider_info(self) -> dict[str, Any]:
        """Return metadata about this provider implementation."""
        return {
            "provider_version": self.PROVIDER_VERSION,
            "class": self.__class__.__name__,
            "module": self.__class__.__module__,
        }


# ═══════════════════════════════════════════════════════════
# STT Provider
# ═══════════════════════════════════════════════════════════

class STTProvider(BaseProvider):
    """Speech-to-Text provider interface.

    Converts audio input into text transcriptions with optional
    speaker diarization, word-level timestamps, and language detection.
    """

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ProviderResult:
        """Transcribe audio to text.

        Args:
            audio_path: Path to the audio file.
            language: Optional language code (e.g., 'en', 'es').
            model: Optional model ID override.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'text', 'segments', and 'language' in data.
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available STT models.

        Returns:
            List of ModelInfo objects describing available models.
        """
        ...

    def transcribe_stream(
        self,
        audio_path: str,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream transcription results in real-time.

        Args:
            audio_path: Path to the audio file.
            **kwargs: Additional provider-specific options.

        Yields:
            Dict with 'text', 'is_final', and 'timestamp' keys.
        """
        raise NotImplementedError("Streaming transcription not supported")

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Returns:
            List of language codes (e.g., ['en', 'es', 'fr']).
        """
        return []


# ═══════════════════════════════════════════════════════════
# Vision Provider
# ═══════════════════════════════════════════════════════════

class VisionProvider(BaseProvider):
    """Vision provider interface for object detection and scene analysis.

    Detects objects, scenes, and visual elements in video frames or images.
    Supports batch processing for efficient frame-by-frame analysis.
    """

    @abstractmethod
    def detect(
        self,
        image_path: str,
        **kwargs: Any,
    ) -> ProviderResult:
        """Detect objects/ scenes in a single image.

        Args:
            image_path: Path to the image file.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'detections' list in data.
        """
        ...

    @abstractmethod
    def detect_batch(
        self,
        image_paths: list[str],
        **kwargs: Any,
    ) -> list[ProviderResult]:
        """Detect objects across multiple images.

        Args:
            image_paths: List of image file paths.
            **kwargs: Additional provider-specific options.

        Returns:
            List of ProviderResult objects, one per image.
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available vision models.

        Returns:
            List of ModelInfo objects.
        """
        ...

    def detect_video(
        self,
        video_path: str,
        frame_interval: int = 30,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Process a video file frame by frame.

        Args:
            video_path: Path to the video file.
            frame_interval: Process every Nth frame.
            **kwargs: Additional provider-specific options.

        Yields:
            Dict with 'frame', 'timestamp', and 'detections' keys.
        """
        raise NotImplementedError("Video detection not supported")


# ═══════════════════════════════════════════════════════════
# LLM Provider
# ═══════════════════════════════════════════════════════════

class LLMProvider(BaseProvider):
    """Large Language Model provider interface.

    Generates text completions from prompts, with support for
    system prompts, temperature, streaming, and structured output.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ProviderResult:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system-level instruction.
            temperature: Sampling temperature (0.0 to 1.0).
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'text' and 'usage' in data.
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available LLM models.

        Returns:
            List of ModelInfo objects.
        """
        ...

    def generate_stream(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream generated text token by token.

        Args:
            prompt: The user prompt.
            **kwargs: Additional provider-specific options.

        Yields:
            Text chunks as they are generated.
        """
        raise NotImplementedError("Streaming generation not supported")

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Args:
            text: The input text.

        Returns:
            Token count.
        """
        # Default: approximate with word count / 0.75
        return int(len(text.split()) / 0.75)


# ═══════════════════════════════════════════════════════════
# Caption Provider
# ═══════════════════════════════════════════════════════════

@dataclass
class CaptionStyle:
    """A caption/subtitle style configuration."""
    name: str = "default"
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    background_color: str = "#00000080"
    position: str = "bottom"  # "top", "bottom", "middle"
    alignment: str = "center"  # "left", "center", "right"


class CaptionProvider(BaseProvider):
    """Caption/subtitle generation provider interface.

    Generates timed captions from audio/video input with configurable
    styles, formats, and output options.
    """

    @abstractmethod
    def generate_captions(
        self,
        media_path: str,
        language: str = "en",
        **kwargs: Any,
    ) -> ProviderResult:
        """Generate captions from media input.

        Args:
            media_path: Path to the media file.
            language: Language code for caption generation.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'captions' list (each with 'start', 'end', 'text').
        """
        ...

    @abstractmethod
    def get_styles(self) -> list[CaptionStyle]:
        """Get available caption styles.

        Returns:
            List of CaptionStyle objects.
        """
        ...

    def export_captions(
        self,
        captions: list[dict[str, Any]],
        output_path: str,
        format: str = "srt",
        style: CaptionStyle | None = None,
    ) -> ProviderResult:
        """Export captions to a subtitle file.

        Args:
            captions: List of caption dicts with 'start', 'end', 'text'.
            output_path: Path to write the subtitle file.
            format: Output format ('srt', 'vtt', 'ass', 'ttml').
            style: Optional caption style.

        Returns:
            ProviderResult indicating success or failure.
        """
        raise NotImplementedError("Caption export not supported")

    def get_supported_formats(self) -> list[str]:
        """Get list of supported caption output formats.

        Returns:
            List of format strings (e.g., ['srt', 'vtt', 'ass']).
        """
        return ["srt", "vtt"]


# ═══════════════════════════════════════════════════════════
# Translation Provider
# ═══════════════════════════════════════════════════════════

class TranslationProvider(BaseProvider):
    """Language translation provider interface.

    Translates text between languages with support for batch
    translation, language detection, and domain-specific terminology.
    """

    @abstractmethod
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs: Any,
    ) -> ProviderResult:
        """Translate text from source to target language.

        Args:
            text: The text to translate.
            source_language: Source language code.
            target_language: Target language code.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'translated_text' in data.
        """
        ...

    @abstractmethod
    def get_supported_languages(self) -> list[dict[str, str]]:
        """Get list of supported languages.

        Returns:
            List of dicts with 'code' and 'name' keys.
        """
        ...

    def translate_batch(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
        **kwargs: Any,
    ) -> list[ProviderResult]:
        """Translate multiple texts in batch.

        Args:
            texts: List of texts to translate.
            source_language: Source language code.
            target_language: Target language code.
            **kwargs: Additional provider-specific options.

        Returns:
            List of ProviderResult objects, one per text.
        """
        results: list[ProviderResult] = []
        for text in texts:
            result = self.translate(text, source_language, target_language, **kwargs)
            results.append(result)
        return results

    def detect_language(self, text: str) -> str:
        """Detect the language of a text.

        Args:
            text: The text to analyze.

        Returns:
            Language code (e.g., 'en', 'es'), or empty string if unknown.
        """
        return ""


# ═══════════════════════════════════════════════════════════
# Export Provider
# ═══════════════════════════════════════════════════════════

@dataclass
class ExportFormat:
    """Information about a supported export format."""
    name: str = ""
    extension: str = ""
    mime_type: str = ""
    description: str = ""
    supports_gpu: bool = False
    supported_codecs: list[str] = field(default_factory=list)


class ExportProvider(BaseProvider):
    """Export provider interface for video/file output.

    Handles encoding and exporting rendered timelines to various
    output formats with configurable quality, resolution, and codec.
    """

    @abstractmethod
    def export(
        self,
        input_path: str,
        output_path: str,
        format: str = "mp4",
        **kwargs: Any,
    ) -> ProviderResult:
        """Export media to a specified output format.

        Args:
            input_path: Path to the input media.
            output_path: Path for the output file.
            format: Output format identifier.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult with 'output_path' and 'metadata' in data.
        """
        ...

    @abstractmethod
    def get_supported_formats(self) -> list[ExportFormat]:
        """Get list of supported export formats.

        Returns:
            List of ExportFormat objects.
        """
        ...

    def estimate_output_size(
        self,
        input_path: str,
        format: str = "mp4",
        quality: str = "high",
    ) -> int:
        """Estimate the output file size in bytes.

        Args:
            input_path: Path to the input media.
            format: Output format.
            quality: Quality level ('low', 'medium', 'high').

        Returns:
            Estimated file size in bytes.
        """
        return 0


__all__ = [
    "BaseProvider",
    "ProviderResult",
    "ModelInfo",
    "STTProvider",
    "VisionProvider",
    "LLMProvider",
    "CaptionProvider",
    "CaptionStyle",
    "TranslationProvider",
    "ExportProvider",
    "ExportFormat",
]
