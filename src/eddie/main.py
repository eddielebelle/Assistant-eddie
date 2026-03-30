"""Eddie Voice Assistant - Thin Client.

Wires together: Microphone → Wake word → Capture → Server (STT+Agent+TTS) → Speaker

Can run in three modes:
1. Voice mode (default): Full pipeline with microphone input and speaker output
2. Text mode (--text): Type commands directly, useful for testing without audio hardware
3. Mic test (--mic-test): Diagnostic to verify mic, wake word, and server connectivity
"""

import argparse
import io
import logging
import signal
import struct
import wave

import requests

from eddie.config import get_config

logger = logging.getLogger(__name__)

# Graceful shutdown flag
_running = True


def _signal_handler(sig, frame):
    global _running
    logger.info("Shutdown signal received")
    _running = False


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, sample_width: int = 2, channels: int = 1) -> bytes:
    """Wrap raw PCM int16 bytes in a WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


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


def run_mic_test():
    """Diagnostic mode: verify mic input, audio levels, wake word, and server round-trip."""
    import time

    import numpy as np
    import pyaudio

    config = get_config()
    agent_url = f"http://{config.agent_host}:{config.agent_port}"
    RATE = 16000
    CHUNK = 1280  # 80ms

    print("=" * 60)
    print("  Eddie Mic & Pipeline Diagnostic")
    print("=" * 60)

    # 1. Agent connectivity
    print("\n[1/5] Agent connectivity")
    try:
        resp = requests.get(f"{agent_url}/health", timeout=5)
        if resp.status_code == 200:
            print(f"  OK  agent reachable at {agent_url}")
        else:
            print(f"  WARN  agent returned status {resp.status_code}")
    except requests.ConnectionError:
        print(f"  FAIL  cannot connect to agent at {agent_url}")
    except Exception as e:
        print(f"  FAIL  {e}")

    # 2. Open mic
    print("\n[2/5] Microphone")
    try:
        pa = pyaudio.PyAudio()
        info = pa.get_default_input_device_info()
        print(f"  OK  device: {info['name']} (channels={int(info['maxInputChannels'])}, rate={int(info['defaultSampleRate'])}Hz)")
    except Exception as e:
        print(f"  FAIL  no input device: {e}")
        return

    try:
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=RATE,
            input=True, frames_per_buffer=CHUNK,
        )
        print(f"  OK  stream opened (16kHz, 16-bit mono, {CHUNK} samples/frame)")
    except Exception as e:
        print(f"  FAIL  cannot open stream: {e}")
        pa.terminate()
        return

    # 3. Audio levels — 3 seconds
    print("\n[3/5] Audio levels (speak now — 3 seconds)")
    peak_rms = 0.0
    chunks_read = 0
    silence_count = 0
    SILENCE_THRESHOLD = 500
    start = time.time()
    while time.time() - start < 3.0:
        raw = stream.read(CHUNK, exception_on_overflow=False)
        chunk = np.frombuffer(raw, dtype=np.int16)
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        peak_rms = max(peak_rms, rms)
        chunks_read += 1
        if rms < SILENCE_THRESHOLD:
            silence_count += 1
        bar = "#" * min(int(rms / 100), 50)
        print(f"\r  RMS: {rms:7.1f}  {bar:<50}", end="", flush=True)
    print()
    print(f"  Peak RMS: {peak_rms:.1f} | Chunks: {chunks_read} | Silent: {silence_count}/{chunks_read}")
    if peak_rms < SILENCE_THRESHOLD:
        print(f"  WARN  peak below silence threshold ({SILENCE_THRESHOLD}) — mic may be muted or too quiet")
    else:
        print(f"  OK  audio detected above threshold")

    # 4. Wake word model
    print("\n[4/5] Wake word")
    if not config.wake_word_model:
        print("  SKIP  no WAKE_WORD_MODEL configured (energy-trigger mode)")
    else:
        try:
            from eddie.stt import wakeword
            wakeword._get_model()
            print(f"  OK  openwakeword loaded (model: {config.wake_word_model}, threshold: {config.wake_word_threshold})")
        except Exception as e:
            print(f"  FAIL  {e}")

    # 5. Server voice round-trip
    print("\n[5/5] Voice round-trip (speak a short phrase — 2 seconds)")
    frames = []
    start = time.time()
    while time.time() - start < 2.0:
        raw = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(raw)
    pcm_data = b"".join(frames)
    wav_data = _pcm_to_wav(pcm_data)

    try:
        resp = requests.post(
            f"{agent_url}/api/voice",
            files={"audio": ("utterance.wav", wav_data, "audio/wav")},
            timeout=30,
            stream=True,
        )
        if resp.status_code == 204:
            print("  WARN  server received audio but detected no speech")
        elif resp.status_code == 200:
            # Read first chunk to confirm audio comes back
            length_bytes = resp.raw.read(4)
            if length_bytes and struct.unpack(">I", length_bytes)[0] > 0:
                print("  OK  server returned audio response")
            else:
                print("  WARN  server returned empty audio")
        else:
            print(f"  FAIL  server returned status {resp.status_code}")
    except requests.ConnectionError:
        print(f"  FAIL  cannot connect to {agent_url}/api/voice")
    except Exception as e:
        print(f"  FAIL  {e}")

    # Cleanup
    stream.stop_stream()
    stream.close()
    pa.terminate()

    print("\n" + "=" * 60)
    print("  Diagnostic complete")
    print("=" * 60)


def run_voice_mode():
    """Thin client voice pipeline: Wake word → Capture → Server → Playback.

    Pipeline stages:
    1. Continuously feed 80ms audio chunks to openwakeword (local)
    2. On wake word detection, capture utterance (VAD-based silence detection)
    3. POST captured audio to server /api/voice
    4. Server runs STT → Agent → TTS, streams back length-prefixed WAV chunks
    5. Play audio chunks as they arrive
    """
    import queue
    import threading
    import time

    import numpy as np
    import pyaudio
    from pydub import AudioSegment
    from pydub.playback import play

    from eddie.stt import wakeword

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
    audio_stream = pa.open(
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
    logger.info("Agent: %s", agent_url)

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

    def _capture_utterance() -> bytes | None:
        """Capture audio until silence is detected. Returns raw PCM bytes."""
        frames = []
        silent_chunks = 0
        max_chunks = int(MAX_CAPTURE_SECONDS * RATE / CHUNK)
        silence_chunks_needed = int(SILENCE_TIMEOUT * RATE / CHUNK)

        for _ in range(max_chunks):
            if not _running:
                return None
            raw = audio_stream.read(CHUNK, exception_on_overflow=False)
            chunk = np.frombuffer(raw, dtype=np.int16)
            frames.append(raw)

            if _rms(chunk) < SILENCE_THRESHOLD:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    break
            else:
                silent_chunks = 0

        if not frames:
            return None
        return b"".join(frames)

    def _voice_request(wav_data: bytes, audio_q: queue.Queue):
        """POST audio to server, read streamed WAV chunks into playback queue."""
        try:
            resp = requests.post(
                f"{agent_url}/api/voice",
                files={"audio": ("utterance.wav", wav_data, "audio/wav")},
                timeout=120,
                stream=True,
            )
            if resp.status_code == 204:
                logger.info("Server detected no speech")
                return
            resp.raise_for_status()

            # Read length-prefixed WAV chunks
            raw_stream = resp.raw
            while True:
                length_bytes = raw_stream.read(4)
                if not length_bytes or len(length_bytes) < 4:
                    break
                chunk_len = struct.unpack(">I", length_bytes)[0]
                if chunk_len == 0:
                    break  # sentinel
                chunk_data = raw_stream.read(chunk_len)
                if chunk_data:
                    audio_q.put(chunk_data)

        except requests.ConnectionError:
            logger.error("Cannot connect to agent service at %s", agent_url)
        except Exception:
            logger.exception("Error in voice request")

    try:
        while _running:
            # Read an 80ms audio chunk
            raw = audio_stream.read(CHUNK, exception_on_overflow=False)
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
            pcm_data = _capture_utterance()
            if pcm_data is None or len(pcm_data) < RATE * 2:  # < 1 second (16-bit = 2 bytes/sample)
                continue

            wav_data = _pcm_to_wav(pcm_data)
            logger.info("Captured %d bytes, sending to server...", len(wav_data))

            # Send to server and play back streamed audio
            audio_q = queue.Queue()
            player = threading.Thread(target=_play_audio_worker, args=(audio_q,), daemon=True)
            player.start()

            _voice_request(wav_data, audio_q)

            # Signal player to finish and wait
            audio_q.put(None)
            player.join()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Eddie Voice Assistant")
    parser.add_argument("--text", action="store_true", help="Run in text mode (no audio)")
    parser.add_argument("--mic-test", action="store_true", help="Run mic & pipeline diagnostic")
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
    logger.info("Eddie v2 starting up")

    if args.mic_test:
        run_mic_test()
    elif args.text:
        run_text_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    main()
