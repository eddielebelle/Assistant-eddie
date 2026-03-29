#!/usr/bin/env python3
"""Audition TTS voices side by side.

Generates audio samples from both Kokoro and Chatterbox (if installed)
so you can compare voices and pick the best one for Eddie.

Usage:
    python scripts/audition_tts.py
    python scripts/audition_tts.py --play          # auto-play each sample
    python scripts/audition_tts.py --text "Hello!"  # custom test phrase
    python scripts/audition_tts.py --backend kokoro --voice bf_emma
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Test phrases that exercise different speech patterns
DEFAULT_PHRASES = [
    "Hello! I'm Eddie, your voice assistant. How can I help you today?",
    "The time in London is quarter past three in the afternoon.",
    "It looks like it'll be cloudy this morning, clearing up by the afternoon with a high of seventeen degrees.",
    "I've set a timer for ten minutes. I'll let you know when it's done.",
    "Now playing Radio by Alkaline Trio.",
]

OUTPUT_DIR = Path("audition_samples")


def audition_kokoro(phrases: list[str], play: bool = False, voices: list[str] | None = None):
    """Generate samples from Kokoro with various British voices."""
    try:
        from kokoro import KPipeline
    except ImportError:
        logger.warning("Kokoro not installed. Run: pip install -e '.[tts-kokoro]'")
        return

    import numpy as np
    import soundfile as sf

    if voices is None:
        voices = [
            # British voices
            "bf_emma",
            "bf_isabella",
            "bf_alice",
            "bf_lily",
            "bm_george",
            "bm_lewis",
            "bm_daniel",
            "bm_fable",
        ]

    out_dir = OUTPUT_DIR / "kokoro"
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = KPipeline(lang_code="b")  # British English

    for voice in voices:
        logger.info("Kokoro voice: %s", voice)
        for i, phrase in enumerate(phrases):
            audio_chunks = []
            for _, _, audio in pipeline(phrase, voice=voice):
                audio_chunks.append(audio)

            if not audio_chunks:
                continue

            full_audio = np.concatenate(audio_chunks)
            filename = out_dir / f"{voice}_sample{i + 1}.wav"
            sf.write(str(filename), full_audio, 24000)
            logger.info("  Saved: %s", filename)

            if play:
                _play_audio(filename)


def audition_chatterbox(phrases: list[str], play: bool = False, ref_audio: str = ""):
    """Generate samples from Chatterbox."""
    try:
        from chatterbox.tts import ChatterboxTTS
    except ImportError:
        logger.warning("Chatterbox not installed. Run: pip install -e '.[tts-chatterbox]'")
        return

    import soundfile as sf

    out_dir = OUTPUT_DIR / "chatterbox"
    out_dir.mkdir(parents=True, exist_ok=True)

    model = ChatterboxTTS.from_pretrained(device="cuda")
    ref = ref_audio if ref_audio else None
    voice_label = Path(ref_audio).stem if ref_audio else "default"

    logger.info("Chatterbox voice: %s", voice_label)
    for i, phrase in enumerate(phrases):
        wav = model.generate(phrase, audio_prompt=ref)
        audio_np = wav.squeeze().cpu().numpy()

        filename = out_dir / f"{voice_label}_sample{i + 1}.wav"
        sf.write(str(filename), audio_np, 24000)
        logger.info("  Saved: %s", filename)

        if play:
            _play_audio(filename)


def _play_audio(path: Path):
    """Play an audio file using the system player."""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["afplay", str(path)], check=False)
    elif sys.platform == "linux":
        subprocess.run(["aplay", str(path)], check=False)
    else:
        logger.info("Auto-play not supported on this platform. Open: %s", path)


def main():
    parser = argparse.ArgumentParser(description="Audition TTS voices for Eddie")
    parser.add_argument("--play", action="store_true", help="Auto-play each sample")
    parser.add_argument("--text", type=str, help="Custom test phrase (overrides defaults)")
    parser.add_argument("--backend", type=str, choices=["kokoro", "chatterbox", "both"], default="both")
    parser.add_argument("--voice", type=str, help="Specific voice name (Kokoro only)")
    parser.add_argument("--ref-audio", type=str, default="", help="Reference audio path (Chatterbox voice cloning)")

    args = parser.parse_args()

    phrases = [args.text] if args.text else DEFAULT_PHRASES

    print(f"\nAudition samples will be saved to: {OUTPUT_DIR.absolute()}/")
    print(f"Test phrases: {len(phrases)}")
    print("-" * 50)

    if args.backend in ("kokoro", "both"):
        voices = [args.voice] if args.voice else None
        audition_kokoro(phrases, play=args.play, voices=voices)

    if args.backend in ("chatterbox", "both"):
        audition_chatterbox(phrases, play=args.play, ref_audio=args.ref_audio)

    print(f"\nDone! Listen to samples in: {OUTPUT_DIR.absolute()}/")
    print("\nTo use your chosen voice, set in .env:")
    print("  TTS_BACKEND=kokoro")
    print("  TTS_KOKORO_VOICE=bf_emma   # or whichever you preferred")
    print("  TTS_KOKORO_LANG=b          # b=British, a=American")
    print("\nOr for Chatterbox with voice cloning:")
    print("  TTS_BACKEND=chatterbox")
    print("  TTS_CHATTERBOX_REF_AUDIO=/path/to/your/voice_sample.wav")


if __name__ == "__main__":
    main()
