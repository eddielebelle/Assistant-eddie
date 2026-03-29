"""Eddie configuration via Pydantic BaseSettings. Loads from .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EddieConfig(BaseSettings):
    """Central configuration for all Eddie services."""

    # MQTT (IoT only)
    mqtt_host: str = "192.168.1.57"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8000"
    spotify_data_path: str = "./resources/spotify_data.json"

    # Weather
    openweather_api_key: str = ""
    weather_locations: dict[str, dict[str, float]] = {
        "home": {"lat": 51.751, "lon": -2.139},
        "cheltenham": {"lat": 51.898, "lon": -2.075},
        "york": {"lat": 53.958, "lon": -1.083},
        "mojacar": {"lat": 37.121, "lon": -1.855},
        "sheffield": {"lat": 53.417, "lon": -1.500},
        "port talbot": {"lat": 51.592, "lon": -3.780},
    }

    # Models
    whisper_model_path: str = ""
    whisper_model_size: str = "small.en"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # Agent
    agent_port: int = 5000

    # Conversation
    max_history_messages: int = 50
    session_idle_timeout: int = 300  # seconds

    # TTS
    tts_backend: str = "kokoro"  # "kokoro", "chatterbox", or "coqui"
    tts_kokoro_voice: str = "bf_emma"  # bf_* = British female, bm_* = British male
    tts_kokoro_lang: str = "b"  # "a" = American, "b" = British
    tts_chatterbox_ref_audio: str = ""  # Path to reference audio for voice cloning (optional)
    tts_coqui_speaker_index: int = 80  # Legacy Coqui VITS speaker
    tts_coqui_model_name: str = "tts_models/en/vctk/vits"

    # Audio
    alarm_sound_path: str = "./resources/alarm1.wav"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_config() -> EddieConfig:
    """Load and return the Eddie configuration."""
    return EddieConfig()
