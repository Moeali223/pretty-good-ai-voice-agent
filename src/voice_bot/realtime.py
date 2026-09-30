"""Provider-neutral realtime voice interface and offline fake session."""

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class RealtimeSessionError(RuntimeError):
    """Raised when a realtime session operation is invalid."""


class RealtimeEventType(StrEnum):
    """Small set of provider events used by the media bridge."""

    AUDIO = "audio"
    SPEECH_STARTED = "speech_started"
    SPEECH_STOPPED = "speech_stopped"
    RESPONSE_DONE = "response_done"
    ERROR = "error"


@dataclass(frozen=True)
class RealtimeEvent:
    """Normalized event returned by a realtime voice provider."""

    type: RealtimeEventType
    audio: bytes | None = None
    message: str | None = None


class RealtimeVoiceSession(Protocol):
    """Operations the media bridge expects from any realtime provider."""

    async def connect(self, instructions: str) -> None:
        """Start a voice session using the fictional-patient instructions."""

    async def send_audio(self, audio: bytes) -> None:
        """Send one caller-audio chunk to the voice session."""

    async def receive_event(self) -> RealtimeEvent:
        """Receive the next normalized provider event."""

    async def interrupt(self) -> None:
        """Cancel the current response after detected barge-in."""

    async def close(self) -> None:
        """Close the voice session."""


class InMemoryRealtimeSession:
    """Deterministic fake session that never opens a network connection."""

    def __init__(self, scripted_events: list[RealtimeEvent] | None = None) -> None:
        self.instructions: str | None = None
        self.received_audio: list[bytes] = []
        self.interruption_count = 0
        self.connected = False
        self.closed = False
        self._events = deque(scripted_events or [])

    async def connect(self, instructions: str) -> None:
        if self.connected or self.closed:
            raise RealtimeSessionError("The fake realtime session cannot reconnect.")
        if not instructions.strip():
            raise RealtimeSessionError("Realtime instructions must not be empty.")
        self.instructions = instructions
        self.connected = True

    async def send_audio(self, audio: bytes) -> None:
        self._require_active()
        if not isinstance(audio, bytes) or not audio:
            raise RealtimeSessionError("Realtime audio must be non-empty bytes.")
        self.received_audio.append(audio)

    async def receive_event(self) -> RealtimeEvent:
        self._require_active()
        if not self._events:
            raise RealtimeSessionError("The fake realtime event queue is empty.")
        return self._events.popleft()

    async def interrupt(self) -> None:
        self._require_active()
        self.interruption_count += 1

    async def close(self) -> None:
        if self.closed:
            return
        self.connected = False
        self.closed = True

    def queue_event(self, event: RealtimeEvent) -> None:
        """Add a scripted event without contacting a provider."""
        if self.closed:
            raise RealtimeSessionError("Cannot queue events after the session closes.")
        self._events.append(event)

    def _require_active(self) -> None:
        if not self.connected or self.closed:
            raise RealtimeSessionError("The fake realtime session is not active.")
