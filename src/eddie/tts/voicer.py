"""VITS Text-to-Speech service for Eddie."""

import logging
import tempfile

logger = logging.getLogger(__name__)

# Lazy-loaded TTS model
_tts = None


def _get_tts():
    """Lazy-load the TTS model."""
    global _tts
    if _tts is None:
        from TTS.api import TTS

        from eddie.config import get_config

        config = get_config()
        logger.info("Loading TTS model: %s", config.tts_model_name)
        _tts = TTS(model_name=config.tts_model_name, progress_bar=False).to("cuda")
        logger.info("TTS model loaded successfully")
    return _tts


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes (WAV format).

    Args:
        text: Text to speak

    Returns:
        WAV audio data as bytes
    """
    if not text or len(text.strip()) < 2:
        text = "I'm not sure what to say."

    tts = _get_tts()

    from eddie.config import get_config

    config = get_config()
    speaker = tts.speakers[config.tts_speaker_index]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tts.tts_to_file(text=text, speaker=speaker, file_path=tmp.name)

        with open(tmp.name, "rb") as f:
            wav_data = f.read()

    logger.info("Synthesized %d bytes of audio for: %s", len(wav_data), text[:100])
    return wav_data


def synthesize_to_file(text: str, output_path: str) -> str:
    """Convert text to speech and save to a file.

    Returns the output file path.
    """
    if not text or len(text.strip()) < 2:
        text = "I'm not sure what to say."

    tts = _get_tts()

    from eddie.config import get_config

    config = get_config()
    speaker = tts.speakers[config.tts_speaker_index]

    tts.tts_to_file(text=text, speaker=speaker, file_path=output_path)
    logger.info("Saved audio to %s for: %s", output_path, text[:100])
    return output_path
