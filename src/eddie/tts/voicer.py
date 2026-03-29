"""Text-to-Speech service for Eddie.

Supports multiple backends:
- kokoro: Fast, lightweight, 54 voices including British English (recommended)
- chatterbox: High quality with voice cloning from reference audio
- coqui: Legacy VITS backend (deprecated, not actively maintained)

Set TTS_BACKEND in .env to choose. Install the corresponding extras:
  pip install -e ".[tts-kokoro]"
  pip install -e ".[tts-chatterbox]"
  pip install -e ".[tts-coqui]"
"""

import logging
import tempfile
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Lazy-loaded backend instance
_backend: "TTSBackend | None" = None


class TTSBackend(ABC):
    """Base class for TTS backends."""

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Convert text to WAV audio bytes."""

    @abstractmethod
    def list_voices(self) -> list[str]:
        """List available voice names."""


class KokoroBackend(TTSBackend):
    """Kokoro TTS - fast, lightweight, multi-voice/multi-language."""

    def __init__(self, voice: str = "bf_emma", lang_code: str = "b") -> None:
        from kokoro import KPipeline

        self.voice = voice
        self.pipeline = KPipeline(lang_code=lang_code)
        logger.info("Kokoro TTS loaded (voice: %s, lang: %s)", voice, lang_code)

    def synthesize(self, text: str) -> bytes:
        import io

        import soundfile as sf

        # Generate audio - pipeline yields (graphemes, phonemes, audio) tuples
        audio_chunks = []
        for _, _, audio in self.pipeline(text, voice=self.voice):
            audio_chunks.append(audio)

        if not audio_chunks:
            logger.warning("Kokoro produced no audio for: %s", text[:100])
            return b""

        # Concatenate chunks
        import numpy as np

        full_audio = np.concatenate(audio_chunks)

        # Write to WAV bytes
        buf = io.BytesIO()
        sf.write(buf, full_audio, 24000, format="WAV")
        wav_data = buf.getvalue()

        logger.info("Kokoro synthesized %d bytes for: %s", len(wav_data), text[:100])
        return wav_data

    def list_voices(self) -> list[str]:
        # Kokoro voice naming: {lang}{gender}_{name}
        # a = American, b = British, f = female, m = male
        return [
            # British voices
            "bf_emma",
            "bf_isabella",
            "bf_alice",
            "bf_lily",
            "bm_george",
            "bm_lewis",
            "bm_daniel",
            "bm_fable",
            # American voices
            "af_heart",
            "af_bella",
            "af_nicole",
            "af_sarah",
            "af_sky",
            "am_adam",
            "am_michael",
            "am_echo",
            "am_liam",
        ]


class ChatterboxBackend(TTSBackend):
    """Chatterbox TTS - high quality with optional voice cloning."""

    def __init__(self, ref_audio_path: str = "") -> None:
        from chatterbox.tts import ChatterboxTTS

        self.model = ChatterboxTTS.from_pretrained(device="cuda")
        self.ref_audio_path = ref_audio_path if ref_audio_path else None
        logger.info(
            "Chatterbox TTS loaded (ref_audio: %s)",
            ref_audio_path or "default voice",
        )

    def synthesize(self, text: str) -> bytes:
        import io

        import soundfile as sf

        wav = self.model.generate(text, audio_prompt=self.ref_audio_path)

        buf = io.BytesIO()
        sf.write(buf, wav.squeeze().cpu().numpy(), 24000, format="WAV")
        wav_data = buf.getvalue()

        logger.info("Chatterbox synthesized %d bytes for: %s", len(wav_data), text[:100])
        return wav_data

    def list_voices(self) -> list[str]:
        return ["default", "custom (provide ref_audio path)"]


class CoquiBackend(TTSBackend):
    """Legacy Coqui VITS backend."""

    def __init__(self, model_name: str = "tts_models/en/vctk/vits", speaker_index: int = 80) -> None:
        from TTS.api import TTS

        self.tts = TTS(model_name=model_name, progress_bar=False).to("cuda")
        self.speaker = self.tts.speakers[speaker_index]
        logger.info("Coqui TTS loaded (model: %s, speaker: %d)", model_name, speaker_index)

    def synthesize(self, text: str) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            self.tts.tts_to_file(text=text, speaker=self.speaker, file_path=tmp.name)
            with open(tmp.name, "rb") as f:
                wav_data = f.read()

        logger.info("Coqui synthesized %d bytes for: %s", len(wav_data), text[:100])
        return wav_data

    def list_voices(self) -> list[str]:
        return [f"speaker_{i}" for i in range(len(self.tts.speakers))]


def _get_backend() -> TTSBackend:
    """Lazy-load the configured TTS backend."""
    global _backend
    if _backend is None:
        from eddie.config import get_config

        config = get_config()
        backend_name = config.tts_backend.lower()

        if backend_name == "kokoro":
            _backend = KokoroBackend(voice=config.tts_kokoro_voice, lang_code=config.tts_kokoro_lang)
        elif backend_name == "chatterbox":
            _backend = ChatterboxBackend(ref_audio_path=config.tts_chatterbox_ref_audio)
        elif backend_name == "coqui":
            _backend = CoquiBackend(
                model_name=config.tts_coqui_model_name,
                speaker_index=config.tts_coqui_speaker_index,
            )
        else:
            raise ValueError(f"Unknown TTS backend: '{backend_name}'. Use 'kokoro', 'chatterbox', or 'coqui'.")

    return _backend


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes (WAV format)."""
    if not text or len(text.strip()) < 2:
        text = "I'm not sure what to say."

    backend = _get_backend()
    return backend.synthesize(text)


def list_voices() -> list[str]:
    """List available voices for the current backend."""
    backend = _get_backend()
    return backend.list_voices()
