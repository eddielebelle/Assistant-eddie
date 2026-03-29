"""Conversation history manager for Eddie agent sessions."""

import logging
import time

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages per-session chat history with idle timeout."""

    def __init__(self, max_messages: int = 50, idle_timeout: int = 300):
        self.max_messages = max_messages
        self.idle_timeout = idle_timeout
        self.messages: list[dict] = []
        self.last_activity: float = time.time()

    def _check_session_expired(self) -> bool:
        """Check if session has expired due to idle timeout."""
        if time.time() - self.last_activity > self.idle_timeout:
            logger.info("Session expired after %d seconds of inactivity", self.idle_timeout)
            self.messages.clear()
            return True
        return False

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self._check_session_expired()
        self.messages.append({"role": role, "content": content})
        self.last_activity = time.time()
        self._trim()

    def add_raw(self, message: dict) -> None:
        """Add a raw message dict (e.g. tool call/response from Ollama)."""
        self._check_session_expired()
        self.messages.append(message)
        self.last_activity = time.time()
        self._trim()

    def get_messages(self, system_prompt: str) -> list[dict]:
        """Return full message list with system prompt prepended."""
        self._check_session_expired()
        return [{"role": "system", "content": system_prompt}, *self.messages]

    def clear(self) -> None:
        """Clear all conversation history."""
        self.messages.clear()
        self.last_activity = time.time()

    def _trim(self) -> None:
        """Trim oldest messages if history exceeds max length."""
        if len(self.messages) > self.max_messages:
            trimmed = len(self.messages) - self.max_messages
            self.messages = self.messages[trimmed:]
            logger.debug("Trimmed %d old messages from history", trimmed)
