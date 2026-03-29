"""Whisper-based Speech-to-Text service for Eddie."""

import logging
import tempfile
import wave

logger = logging.getLogger(__name__)

# Lazy-loaded whisper model
_model = None


def _get_model():
    """Lazy-load the Whisper model."""
    global _model
    if _model is None:
        import whisper

        from eddie.config import get_config

        config = get_config()
        model_path = config.whisper_model_path
        model_size = config.whisper_model_size

        if model_path:
            logger.info("Loading Whisper model from %s", model_path)
            _model = whisper.load_model(model_path)
        else:
            logger.info("Loading Whisper model: %s", model_size)
            _model = whisper.load_model(model_size)

        logger.info("Whisper model loaded successfully")
    return _model


def transcribe(audio_data: bytes, sample_rate: int = 16000, sample_width: int = 2) -> str:
    """Transcribe audio bytes to text using Whisper.

    Args:
        audio_data: Raw audio bytes (PCM format)
        sample_rate: Audio sample rate in Hz
        sample_width: Bytes per sample (2 = 16-bit)

    Returns:
        Transcribed text string
    """
    model = _get_model()

    # Write audio to temp WAV file (Whisper expects a file path)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)

        result = model.transcribe(tmp.name, fp16=False)

    text = result.get("text", "").strip()
    logger.info("Transcribed: %s", text[:200])
    return text


def transcribe_file(file_path: str) -> str:
    """Transcribe an audio file to text."""
    model = _get_model()
    result = model.transcribe(file_path, fp16=False)
    text = result.get("text", "").strip()
    logger.info("Transcribed file %s: %s", file_path, text[:200])
    return text
