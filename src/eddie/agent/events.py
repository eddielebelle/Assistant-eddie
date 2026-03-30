"""Real-time event stream for monitoring Eddie agent activity."""

import json
import queue
import time
import threading

_listeners: list[queue.Queue] = []
_lock = threading.Lock()


def emit(event_type: str, data: dict) -> None:
    """Broadcast an event to all connected listeners."""
    event = {"type": event_type, "ts": time.time(), **data}
    with _lock:
        dead = []
        for q in _listeners:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _listeners.remove(q)


def subscribe() -> queue.Queue:
    """Subscribe to the event stream. Returns a queue to read from."""
    q = queue.Queue(maxsize=256)
    with _lock:
        _listeners.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    """Unsubscribe from the event stream."""
    with _lock:
        if q in _listeners:
            _listeners.remove(q)


def stream_sse(q: queue.Queue):
    """Generator that yields SSE-formatted events from a queue."""
    while True:
        try:
            event = q.get(timeout=30)
            yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            # Send keepalive
            yield ": keepalive\n\n"
