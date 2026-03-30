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


def run_voice_mode():
    """Full voice pipeline: Microphone → STT → Agent → TTS → Speaker."""
    import io
    import time

    import speech_recognition as sr
    from pydub import AudioSegment
    from pydub.playback import play

    from eddie.stt.whisper_stt import transcribe
    from eddie.tts.voicer import synthesize

    config = get_config()
    agent_url = f"http://{config.agent_host}:{config.agent_port}"

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    # Calibrate for ambient noise
    logger.info("Calibrating microphone for ambient noise...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=2)

    logger.info("Eddie is listening! (Ctrl+C to quit)")
    logger.info("Agent: %s | Model: %s", agent_url, config.ollama_model)

    while _running:
        try:
            # Listen for voice input
            with mic as source:
                logger.debug("Listening...")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

            # Transcribe with Whisper
            audio_data = audio.get_wav_data()
            text = transcribe(audio_data)

            if not text or len(text.strip()) < 2:
                continue

            logger.info("Heard: %s", text)

            # Send to agent (streaming)
            response = "".join(chat_via_agent(text, agent_url, stream=True))
            logger.info("Eddie says: %s", response)

            if response:
                # Synthesize speech
                wav_data = synthesize(response)

                # Play audio
                audio_segment = AudioSegment.from_wav(io.BytesIO(wav_data))
                play(audio_segment)

        except sr.WaitTimeoutError:
            continue
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception:
            logger.exception("Error in voice loop")
            time.sleep(1)


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
