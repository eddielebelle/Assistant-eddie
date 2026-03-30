"""Voice endpoint: accepts audio, returns streamed TTS audio.

POST /api/voice — thin clients send captured audio (WAV), server runs
STT → agent → TTS and streams back length-prefixed WAV chunks.

Wire format (response):
  [4-byte big-endian uint32 length][WAV bytes] ... [4-byte zero sentinel]
Each chunk is one synthesized sentence.
"""

import logging
import struct

from flask import Blueprint, Response, request

voice_bp = Blueprint("voice", __name__)
logger = logging.getLogger(__name__)


def _sentence_splitter(token_stream):
    """Buffer streamed tokens and yield complete sentences as soon as they're ready."""
    buf = ""
    for token in token_stream:
        buf += token
        while True:
            best = -1
            for delim in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                idx = buf.find(delim)
                if idx != -1 and (best == -1 or idx < best):
                    best = idx + 1  # include the punctuation, not the space
            if best == -1:
                break
            sentence = buf[:best].strip()
            buf = buf[best:]
            if sentence:
                yield sentence
    remainder = buf.strip()
    if remainder:
        yield remainder


@voice_bp.route("/api/voice", methods=["POST"])
def api_voice():
    """Accept audio, run STT → agent → TTS, stream back audio chunks."""
    from eddie.stt.whisper_stt import transcribe
    from eddie.tts.voicer import synthesize

    # Get audio from request
    if "audio" in request.files:
        audio_data = request.files["audio"].read()
    elif request.data:
        audio_data = request.data
    else:
        return {"error": "No audio data provided"}, 400

    # STT
    import numpy as np
    audio_np = np.frombuffer(audio_data, dtype=np.int16) if not audio_data[:4] == b"RIFF" else None

    if audio_np is None:
        # WAV file — strip header, extract PCM
        import io
        import wave

        with wave.open(io.BytesIO(audio_data), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            audio_np = np.frombuffer(raw, dtype=np.int16)

    text = transcribe(audio_np)
    if not text or len(text.strip()) < 2:
        logger.info("Voice request: no speech detected")
        return {"error": "No speech detected"}, 204

    logger.info("Voice request transcribed: %s", text)

    # Stream agent response → TTS → length-prefixed WAV chunks
    from eddie.agent.agent import chat_stream_tokens

    def generate():
        token_stream = chat_stream_tokens(text)
        for sentence in _sentence_splitter(token_stream):
            logger.info("Synthesizing: %s", sentence)
            wav_data = synthesize(sentence)
            if wav_data:
                yield struct.pack(">I", len(wav_data))
                yield wav_data
        # Zero sentinel
        yield struct.pack(">I", 0)

    return Response(generate(), mimetype="application/octet-stream")
