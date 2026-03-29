"""Timer tool for Eddie."""

import logging
import re
import threading
import time

from word2number import w2n

logger = logging.getLogger(__name__)


class TimerManager:
    """Manages named timers with threading-based countdowns."""

    def __init__(self) -> None:
        self._timers: dict[str, dict] = {}
        self._counter: int = 0

    @staticmethod
    def parse_duration(duration_str: str) -> int | None:
        """Parse a natural language duration string into seconds.

        Supports: '5 minutes', 'two hours', '30 seconds', 'ten minutes'
        """
        words = duration_str.split()
        converted = []
        for word in words:
            try:
                converted.append(str(w2n.word_to_num(word)))
            except ValueError:
                converted.append(word)

        text = " ".join(converted)
        match = re.search(r"(\d+)\s*(second|minute|hour)s?", text)
        if match:
            num, unit = match.groups()
            num = int(num)
            if unit == "minute":
                num *= 60
            elif unit == "hour":
                num *= 3600
            return num

        # Try bare number (assume seconds)
        digits = re.findall(r"\d+", text)
        if digits:
            return int(digits[0])

        return None

    def set_timer(self, duration: str, label: str = "") -> str:
        """Set a new timer."""
        seconds = self.parse_duration(duration)
        if seconds is None:
            return f"I couldn't understand the duration '{duration}'. Try something like '5 minutes'."

        if not label:
            self._counter += 1
            label = f"timer-{self._counter}"

        timer_thread = threading.Timer(seconds, self._on_expire, args=[label])
        timer_thread.daemon = True
        timer_thread.start()

        self._timers[label] = {
            "duration": seconds,
            "start_time": time.time(),
            "thread": timer_thread,
        }

        duration_str = f"{seconds / 60:.0f} minutes" if seconds >= 60 else f"{seconds} seconds"

        logger.info("Timer '%s' set for %s", label, duration_str)
        return f"Timer '{label}' set for {duration_str}."

    def cancel_timer(self, label: str = "") -> str:
        """Cancel an active timer."""
        if not label:
            # Cancel most recent
            if not self._timers:
                return "No active timers to cancel."
            label = list(self._timers.keys())[-1]

        if label not in self._timers:
            return f"No timer named '{label}' found."

        self._timers[label]["thread"].cancel()
        del self._timers[label]
        logger.info("Timer '%s' cancelled", label)
        return f"Timer '{label}' has been cancelled."

    def check_timer(self, label: str = "") -> str:
        """Check remaining time on a timer."""
        if not label:
            if not self._timers:
                return "No active timers."
            label = list(self._timers.keys())[-1]

        if label not in self._timers:
            return f"No timer named '{label}' found."

        info = self._timers[label]
        elapsed = time.time() - info["start_time"]
        remaining = max(info["duration"] - elapsed, 0)

        if remaining <= 0:
            del self._timers[label]
            return f"Timer '{label}' has expired."
        elif remaining >= 60:
            return f"Timer '{label}' has {remaining / 60:.1f} minutes remaining."
        else:
            return f"Timer '{label}' has {remaining:.0f} seconds remaining."

    def _on_expire(self, label: str) -> None:
        """Called when a timer expires."""
        logger.info("Timer '%s' expired!", label)
        if label in self._timers:
            del self._timers[label]
        # TODO: trigger alarm sound via TTS/audio service
