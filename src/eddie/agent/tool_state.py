"""Persistent tool state manager. Survives session resets."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TimerState:
    """State of an active timer."""

    duration_seconds: float
    start_time: float
    label: str = ""

    @property
    def remaining_seconds(self) -> float:
        import time

        elapsed = time.time() - self.start_time
        return max(self.duration_seconds - elapsed, 0)

    @property
    def is_expired(self) -> bool:
        return self.remaining_seconds <= 0


@dataclass
class PlaybackState:
    """State of current music playback."""

    track: str = ""
    artist: str = ""
    is_playing: bool = False


@dataclass
class ToolStateManager:
    """Tracks persistent state across conversation sessions.

    This state is injected into the system prompt so Eddie always knows
    what's currently active, even after a session reset.
    """

    timers: dict[str, TimerState] = field(default_factory=dict)
    playback: PlaybackState = field(default_factory=PlaybackState)
    device_states: dict[str, str] = field(default_factory=dict)

    def get_state_summary(self) -> str:
        """Generate a summary of active tool state for the system prompt."""
        parts = []

        # Active timers
        active_timers = {k: v for k, v in self.timers.items() if not v.is_expired}
        if active_timers:
            for name, timer in active_timers.items():
                remaining = timer.remaining_seconds
                time_str = f"{remaining / 60:.1f} minutes" if remaining >= 60 else f"{remaining:.0f} seconds"
                parts.append(f"Timer '{name}': {time_str} remaining")

        # Clean up expired timers
        expired = [k for k, v in self.timers.items() if v.is_expired]
        for k in expired:
            del self.timers[k]

        # Music playback
        if self.playback.is_playing:
            parts.append(f"Now playing: {self.playback.track} by {self.playback.artist}")

        # Device states
        for device, state in self.device_states.items():
            parts.append(f"{device}: {state}")

        if not parts:
            return ""

        return "Active state:\n" + "\n".join(f"- {p}" for p in parts)

    def set_timer(self, name: str, duration_seconds: float) -> None:
        import time

        self.timers[name] = TimerState(
            duration_seconds=duration_seconds,
            start_time=time.time(),
            label=name,
        )
        logger.info("Timer '%s' set for %.0f seconds", name, duration_seconds)

    def cancel_timer(self, name: str) -> bool:
        if name in self.timers:
            del self.timers[name]
            logger.info("Timer '%s' cancelled", name)
            return True
        return False

    def update_playback(self, track: str, artist: str, is_playing: bool = True) -> None:
        self.playback = PlaybackState(track=track, artist=artist, is_playing=is_playing)

    def set_device_state(self, device: str, state: str) -> None:
        self.device_states[device] = state
