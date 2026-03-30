"""Wake word detection using openwakeword.

Provides a continuous audio listener that detects a wake word and then
captures the following utterance for transcription.

Audio specs: 16kHz, 16-bit mono PCM — shared with faster-whisper.
openwakeword processes in 80ms chunks (1280 samples).
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model
_oww_model = None

CHUNK_SAMPLES = 1280  # 80ms at 16kHz — openwakeword's native frame size
SAMPLE_RATE = 16000


def _get_model():
    """Lazy-load the openwakeword model."""
    global _oww_model
    if _oww_model is None:
        import openwakeword
        from openwakeword.model import Model

        from eddie.config import get_config

        config = get_config()

        # Download default models if no custom model specified
        openwakeword.utils.download_models()

        model_paths = [config.wake_word_model] if config.wake_word_model else []
        _oww_model = Model(wakeword_models=model_paths, inference_framework="onnx")
        logger.info(
            "openwakeword loaded (models: %s, threshold: %s)",
            list(_oww_model.models.keys()),
            config.wake_word_threshold,
        )
    return _oww_model


def detect(audio_chunk: np.ndarray, threshold: float | None = None) -> str | None:
    """Feed an 80ms audio chunk and check for wake word detection.

    Args:
        audio_chunk: int16 numpy array, 1280 samples at 16kHz
        threshold: Detection threshold (0-1). Uses config default if None.

    Returns:
        Name of detected wake word, or None.
    """
    if threshold is None:
        from eddie.config import get_config

        threshold = get_config().wake_word_threshold

    model = _get_model()
    predictions = model.predict(audio_chunk)

    for wake_word, score in predictions.items():
        if score >= threshold:
            logger.info("Wake word detected: %s (score=%.3f)", wake_word, score)
            model.reset()
            return wake_word

    return None


def reset():
    """Reset the wake word model state (call after detection)."""
    if _oww_model is not None:
        _oww_model.reset()
