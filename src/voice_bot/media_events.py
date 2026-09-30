"""Parse Twilio-like Media Stream messages without opening a WebSocket."""

import base64
import binascii
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from voice_bot.scenarios import get_scenario


class MediaEventError(ValueError):
    """Raised when an incoming media event is malformed or unsupported."""


class MediaEventType(StrEnum):
    """Twilio message types handled by the first media parser."""

    CONNECTED = "connected"
    START = "start"
    MEDIA = "media"
    MARK = "mark"
    STOP = "stop"


@dataclass(frozen=True)
class ParsedMediaEvent:
    """Validated fields needed by the live audio bridge."""

    event: MediaEventType
    stream_sid: str | None = None
    call_sid: str | None = None
    sequence_number: int | None = None
    scenario_id: str | None = None
    audio: bytes | None = None
    media_timestamp_ms: int | None = None
    mark_name: str | None = None


def _validate_stream_sid(stream_sid: str) -> None:
    """Require a non-empty stream identifier for outbound messages."""
    if not isinstance(stream_sid, str) or not stream_sid.strip():
        raise MediaEventError("streamSid must be a non-empty string.")


def build_outbound_media_message(stream_sid: str, mulaw_audio: bytes) -> str:
    """Build, but do not send, one outbound mulaw audio message."""
    _validate_stream_sid(stream_sid)
    if not isinstance(mulaw_audio, bytes) or not mulaw_audio:
        raise MediaEventError("Outbound audio must be non-empty bytes.")

    return json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(mulaw_audio).decode("ascii"),
            },
        }
    )


def build_mark_message(stream_sid: str, name: str) -> str:
    """Build, but do not send, one playback marker message."""
    _validate_stream_sid(stream_sid)
    if not isinstance(name, str) or not name.strip():
        raise MediaEventError("Mark name must be a non-empty string.")

    return json.dumps(
        {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {"name": name},
        }
    )


def build_clear_message(stream_sid: str) -> str:
    """Build, but do not send, a command that clears buffered call audio."""
    _validate_stream_sid(stream_sid)
    return json.dumps({"event": "clear", "streamSid": stream_sid})


def _required_object(message: dict[str, Any], name: str) -> dict[str, Any]:
    """Return a required nested JSON object."""
    value = message.get(name)
    if not isinstance(value, dict):
        raise MediaEventError(f"{name} must be a JSON object.")
    return value


def _required_text(message: dict[str, Any], name: str) -> str:
    """Return a required non-empty string."""
    value = message.get(name)
    if not isinstance(value, str) or not value:
        raise MediaEventError(f"{name} must be a non-empty string.")
    return value


def _sequence_number(message: dict[str, Any]) -> int:
    """Parse Twilio's string sequence number as a positive integer."""
    raw_sequence = _required_text(message, "sequenceNumber")
    try:
        sequence = int(raw_sequence)
    except ValueError as error:
        raise MediaEventError("sequenceNumber must be an integer string.") from error
    if sequence < 1:
        raise MediaEventError("sequenceNumber must be positive.")
    return sequence


def parse_media_event(raw_message: str) -> ParsedMediaEvent:
    """Validate one JSON message from a Twilio-like media stream."""
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError as error:
        raise MediaEventError("Media event is not valid JSON.") from error

    if not isinstance(message, dict):
        raise MediaEventError("Media event must be a JSON object.")

    try:
        event_type = MediaEventType(message.get("event"))
    except ValueError as error:
        raise MediaEventError("Unsupported media event type.") from error

    if event_type is MediaEventType.CONNECTED:
        if message.get("protocol") != "Call":
            raise MediaEventError("Connected event protocol must be Call.")
        _required_text(message, "version")
        return ParsedMediaEvent(event=event_type)

    stream_sid = _required_text(message, "streamSid")
    sequence = _sequence_number(message)

    if event_type is MediaEventType.START:
        start = _required_object(message, "start")
        call_sid = _required_text(start, "callSid")
        media_format = _required_object(start, "mediaFormat")
        if (
            media_format.get("encoding") != "audio/x-mulaw"
            or media_format.get("sampleRate") != 8000
            or media_format.get("channels") != 1
        ):
            raise MediaEventError("Unsupported Twilio media format.")

        custom_parameters = _required_object(start, "customParameters")
        scenario_id = _required_text(custom_parameters, "scenario_id")
        get_scenario(scenario_id)
        return ParsedMediaEvent(
            event=event_type,
            stream_sid=stream_sid,
            call_sid=call_sid,
            sequence_number=sequence,
            scenario_id=scenario_id,
        )

    if event_type is MediaEventType.MEDIA:
        media = _required_object(message, "media")
        if media.get("track") != "inbound":
            raise MediaEventError("Only inbound audio is accepted from Twilio.")
        payload = _required_text(media, "payload")
        try:
            audio = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as error:
            raise MediaEventError("Media payload must be valid base64.") from error
        if not audio:
            raise MediaEventError("Media payload must not be empty.")
        try:
            timestamp = int(_required_text(media, "timestamp"))
        except ValueError as error:
            raise MediaEventError("Media timestamp must be an integer string.") from error
        return ParsedMediaEvent(
            event=event_type,
            stream_sid=stream_sid,
            sequence_number=sequence,
            audio=audio,
            media_timestamp_ms=timestamp,
        )

    if event_type is MediaEventType.MARK:
        mark = _required_object(message, "mark")
        return ParsedMediaEvent(
            event=event_type,
            stream_sid=stream_sid,
            sequence_number=sequence,
            mark_name=_required_text(mark, "name"),
        )

    stop = _required_object(message, "stop")
    return ParsedMediaEvent(
        event=event_type,
        stream_sid=stream_sid,
        call_sid=_required_text(stop, "callSid"),
        sequence_number=sequence,
    )
