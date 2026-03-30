"""Speech-to-Text service for Eddie using faster-whisper.

faster-whisper is a CTranslate2-based reimplementation of OpenAI's Whisper
that runs ~4x faster with the same accuracy. Supports CPU (int8) and GPU
(float16) inference.
"""

import io
import logging
import tempfile
import wave

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def _get_model():
    """Lazy-load the faster-whisper model."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        from eddie.config import get_config

        config = get_config()
        model_size = config.whisper_model_size

        # Auto-detect best device/compute type
        compute_type = config.whisper_compute_type
        device = config.whisper_device

        logger.info("Loading faster-whisper model: %s (device=%s, compute=%s)", model_size, device, compute_type)
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("faster-whisper model loaded successfully")
    return _model


def transcribe(audio_data: bytes, sample_rate: int = 16000, sample_width: int = 2) -> str:
    """Transcribe audio bytes to text using faster-whisper.

    Args:
        audio_data: Raw audio bytes (WAV or PCM format)
        sample_rate: Audio sample rate in Hz
        sample_width: Bytes per sample (2 = 16-bit)

    Returns:
        Transcribed text string
    """
    model = _get_model()

    # Convert raw PCM bytes to float32 numpy array
    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    segments, info = model.transcribe(
        audio_np,
        language="en",
        beam_size=5,
        vad_filter=True,
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()
    logger.info("Transcribed: %s", text[:200])
    return text


def transcribe_file(file_path: str) -> str:
    """Transcribe an audio file to text."""
    model = _get_model()
    segments, info = model.transcribe(
        file_path,
        language="en",
        beam_size=5,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    logger.info("Transcribed file %s: %s", file_path, text[:200])
    return text
