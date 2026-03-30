"""Eddie Voice Assistant - Main Entry Point.

Wires together: Microphone → STT → Agent → TTS → Speaker

Can run in two modes:
1. Voice mode (default): Full pipeline with microphone input and speaker output
2. Text mode (--text): Type commands directly, useful for testing without audio hardware
"""

import argparse
import logging
import signal

import requests

from eddie.config import get_config

logger = logging.getLogger(__name__)

# Graceful shutdown flag
_running = True


def _signal_handler(sig, frame):
    global _running
    logger.info("Shutdown signal received")
    _running = False


def chat_via_agent(text: str, agent_url: str, stream: bool = False):
    """Send text to the Eddie agent service and get a response.

    When stream=True, yields tokens as they arrive (NDJSON).
    When stream=False, returns the full response string.
    """
    import json

    try:
        resp = requests.post(
            f"{agent_url}/api/chat",
            json={"text": text, "stream": stream},
            timeout=120,
            stream=stream,
        )
        resp.raise_for_status()

        if not stream:
            return resp.json().get("response", "")

        # Yield tokens as they arrive
        full_response = ""
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "token" in data:
                full_response += data["token"]
                yield data["token"]
            if data.get("done"):
                return

        return full_response

    except requests.ConnectionError:
        logger.error("Cannot connect to agent service at %s", agent_url)
        msg = "I can't reach my brain right now. Is the agent service running?"
        if stream:
            yield msg
        else:
            return msg
    except Exception:
        logger.exception("Error communicating with agent service")
        msg = "Something went wrong while processing your request."
        if stream:
            yield msg
        else:
            return msg


def run_text_mode():
    """Interactive text mode for testing without audio hardware."""
    config = get_config()
    agent_url = f"http://{config.agent_host}:{config.agent_port}"

    print("Eddie Text Mode - Type your commands (Ctrl+C to quit)")
    print(f"Agent: {agent_url} | Model: {config.ollama_model}")
    print("-" * 50)

    while _running:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            print("\nEddie: ", end="", flush=True)
            for token in chat_via_agent(user_input, agent_url, stream=True):
                print(token, end="", flush=True)
            print()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def _sentence_splitter(token_stream):
    """Buffer streamed tokens and yield complete sentences as soon as they're ready."""
    buf = ""
    for token in token_stream:
        buf += token
        # Split on sentence-ending punctuation followed by a space or end
        while True:
            # Find the earliest sentence boundary
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
    # Flush remainder
    remainder = buf.strip()
    if remainder:
        yield remainder


def run_voice_mode():
    """Full voice pipeline: Wake word → STT → Agent (streaming) → TTS → Speaker.

    Pipeline stages:
    1. Continuously feed 80ms audio chunks to openwakeword
    2. On wake word detection, capture utterance (VAD-based silence detection)
    3. Transcribe captured audio with faster-whisper
    4. Stream agent response, synthesize and play sentence-by-sentence
    """
    import io
    import queue
    import struct
    import threading
    import time

    import numpy as np
    import pyaudio
    from pydub import AudioSegment
    from pydub.playback import play

    from eddie.stt import wakeword
    from eddie.stt.whisper_stt import transcribe
    from eddie.tts.voicer import synthesize

    config = get_config()
    agent_url = f"http://{config.agent_host}:{config.agent_port}"
    use_wake_word = bool(config.wake_word_model)

    RATE = 16000
    CHUNK = wakeword.CHUNK_SAMPLES  # 1280 samples = 80ms

    # Silence detection parameters
    SILENCE_THRESHOLD = 500        # RMS amplitude below this = silence
    SILENCE_TIMEOUT = 1.5          # seconds of silence to end capture
    MAX_CAPTURE_SECONDS = 15       # max utterance length

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    if use_wake_word:
        logger.info("Eddie listening for wake word (Ctrl+C to quit)")
    else:
        logger.info("Eddie listening (no wake word, always on) (Ctrl+C to quit)")
    logger.info("Agent: %s | Model: %s", agent_url, config.ollama_model)

    def _rms(data: np.ndarray) -> float:
        """Root mean square of audio chunk."""
        return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

    def _play_audio_worker(audio_queue: queue.Queue):
        """Background thread that plays audio segments in order."""
        while True:
            item = audio_queue.get()
            if item is None:
                break
            try:
                audio_segment = AudioSegment.from_wav(io.BytesIO(item))
                play(audio_segment)
            except Exception:
                logger.exception("Error playing audio")

    def _capture_utterance() -> np.ndarray | None:
        """Capture audio until silence is detected. Returns int16 numpy array."""
        frames = []
        silent_chunks = 0
        max_chunks = int(MAX_CAPTURE_SECONDS * RATE / CHUNK)
        silence_chunks_needed = int(SILENCE_TIMEOUT * RATE / CHUNK)

        for _ in range(max_chunks):
            if not _running:
                return None
            raw = stream.read(CHUNK, exception_on_overflow=False)
            chunk = np.frombuffer(raw, dtype=np.int16)
            frames.append(chunk)

            if _rms(chunk) < SILENCE_THRESHOLD:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    break
            else:
                silent_chunks = 0

        if not frames:
            return None
        return np.concatenate(frames)

    try:
        while _running:
            # Read an 80ms audio chunk
            raw = stream.read(CHUNK, exception_on_overflow=False)
            chunk = np.frombuffer(raw, dtype=np.int16)

            # Wake word gate
            if use_wake_word:
                detected = wakeword.detect(chunk)
                if not detected:
                    continue
                logger.info("Wake word detected — listening for command...")
            else:
                # No wake word: trigger on any significant audio
                if _rms(chunk) < SILENCE_THRESHOLD:
                    continue

            # Capture the full utterance
            audio_data = _capture_utterance()
            if audio_data is None or len(audio_data) < RATE:  # < 1 second
                continue

            # Transcribe with faster-whisper
            text = transcribe(audio_data)
            if not text or len(text.strip()) < 2:
                continue

            logger.info("Heard: %s", text)

            # Stream response, synthesize and play sentence-by-sentence
            audio_q = queue.Queue()
            player = threading.Thread(target=_play_audio_worker, args=(audio_q,), daemon=True)
            player.start()

            token_stream = chat_via_agent(text, agent_url, stream=True)
            full_response = []

            for sentence in _sentence_splitter(token_stream):
                logger.info("Synthesizing: %s", sentence)
                full_response.append(sentence)
                wav_data = synthesize(sentence)
                if wav_data:
                    audio_q.put(wav_data)

            # Signal player to finish and wait
            audio_q.put(None)
            player.join()

            logger.info("Eddie said: %s", " ".join(full_response))

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Eddie Voice Assistant")
    parser.add_argument("--text", action="store_true", help="Run in text mode (no audio)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    config = get_config()
    logger.info("Eddie v2 starting up (model: %s)", config.ollama_model)

    if args.text:
        run_text_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    main()
