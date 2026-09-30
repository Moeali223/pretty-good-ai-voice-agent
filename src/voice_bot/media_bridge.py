"""Coordinate Twilio-like events with a provider-neutral realtime session."""

from voice_bot.media_events import (
    MediaEventType,
    build_clear_message,
    build_mark_message,
    build_outbound_media_message,
    parse_media_event,
)
from voice_bot.prompts import build_patient_prompt
from voice_bot.realtime import RealtimeEvent, RealtimeEventType, RealtimeVoiceSession
from voice_bot.scenarios import get_scenario


class MediaBridgeError(RuntimeError):
    """Raised when media events arrive in an unsafe or invalid order."""


class MediaBridge:
    """Offline-testable coordinator for the live audio connection."""

    def __init__(self, realtime_session: RealtimeVoiceSession) -> None:
        self.realtime_session = realtime_session
        self.connected = False
        self.stream_sid: str | None = None
        self.scenario_id: str | None = None
        self.pending_marks: set[str] = set()
        self._response_number = 0
        self._response_active = False

    async def process_twilio_message(self, raw_message: str) -> list[str]:
        """Handle one incoming Twilio-like message without transmitting output."""
        event = parse_media_event(raw_message)

        if event.event is MediaEventType.CONNECTED:
            if self.connected:
                raise MediaBridgeError("The media stream is already connected.")
            self.connected = True
            return []

        if not self.connected:
            raise MediaBridgeError("A connected event must arrive first.")

        if event.event is MediaEventType.START:
            if self.stream_sid is not None:
                raise MediaBridgeError("The media stream has already started.")
            self.stream_sid = event.stream_sid
            self.scenario_id = event.scenario_id
            scenario = get_scenario(event.scenario_id or "")
            await self.realtime_session.connect(build_patient_prompt(scenario))
            return []

        self._require_active_stream(event.stream_sid)

        if event.event is MediaEventType.MEDIA:
            await self.realtime_session.send_audio(event.audio or b"")
            return []

        if event.event is MediaEventType.MARK:
            if event.mark_name:
                self.pending_marks.discard(event.mark_name)
            return []

        await self.realtime_session.close()
        self.connected = False
        self.stream_sid = None
        return []

    async def process_realtime_event(self, event: RealtimeEvent) -> list[str]:
        """Convert one normalized AI event into unsent Twilio messages."""
        stream_sid = self._require_active_stream(self.stream_sid)

        if event.type is RealtimeEventType.AUDIO:
            if not event.audio:
                raise MediaBridgeError("Realtime audio event must contain audio bytes.")
            self._response_number += 1
            self._response_active = True
            mark_name = f"response-{self._response_number}"
            self.pending_marks.add(mark_name)
            return [
                build_outbound_media_message(stream_sid, event.audio),
                build_mark_message(stream_sid, mark_name),
            ]

        if event.type is RealtimeEventType.SPEECH_STARTED:
            if not self._response_active:
                return []
            self._response_active = False
            await self.realtime_session.interrupt()
            self.pending_marks.clear()
            return [build_clear_message(stream_sid)]

        if event.type is RealtimeEventType.RESPONSE_DONE:
            self._response_active = False
            return []

        if event.type is RealtimeEventType.ERROR:
            if event.message == "Cancellation failed: no active response found":
                self._response_active = False
                return []
            raise MediaBridgeError(event.message or "Realtime provider reported an error.")

        return []

    def _require_active_stream(self, event_stream_sid: str | None) -> str:
        """Return the current stream ID after checking message ownership."""
        if self.stream_sid is None:
            raise MediaBridgeError("A start event must arrive before media events.")
        if event_stream_sid != self.stream_sid:
            raise MediaBridgeError("Media event belongs to a different stream.")
        return self.stream_sid
