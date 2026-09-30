"""Tests for offline Twilio-like Media Stream parsing."""

import base64
import json
import unittest

from voice_bot.media_events import (
    MediaEventError,
    MediaEventType,
    build_clear_message,
    build_mark_message,
    build_outbound_media_message,
    parse_media_event,
)
from voice_bot.scenarios import ScenarioError


def encoded(message: dict) -> str:
    """Encode a fake event as WebSocket-style JSON text."""
    return json.dumps(message)


class MediaEventTests(unittest.TestCase):
    def test_builds_outbound_media_message(self) -> None:
        audio = b"fake mulaw response"

        message = json.loads(build_outbound_media_message("MZ-fake", audio))

        self.assertEqual(message["event"], "media")
        self.assertEqual(message["streamSid"], "MZ-fake")
        self.assertEqual(
            base64.b64decode(message["media"]["payload"]),
            audio,
        )

    def test_builds_mark_message(self) -> None:
        message = json.loads(build_mark_message("MZ-fake", "response-1"))

        self.assertEqual(
            message,
            {
                "event": "mark",
                "streamSid": "MZ-fake",
                "mark": {"name": "response-1"},
            },
        )

    def test_builds_clear_message_for_interruption(self) -> None:
        message = json.loads(build_clear_message("MZ-fake"))

        self.assertEqual(
            message,
            {"event": "clear", "streamSid": "MZ-fake"},
        )

    def test_outbound_messages_reject_missing_stream_id(self) -> None:
        with self.assertRaises(MediaEventError):
            build_clear_message("")

    def test_outbound_media_rejects_empty_audio(self) -> None:
        with self.assertRaises(MediaEventError):
            build_outbound_media_message("MZ-fake", b"")

    def test_mark_rejects_empty_name(self) -> None:
        with self.assertRaises(MediaEventError):
            build_mark_message("MZ-fake", "")

    def test_parses_connected_event(self) -> None:
        event = parse_media_event(
            encoded({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        )

        self.assertEqual(event.event, MediaEventType.CONNECTED)

    def test_parses_start_event_and_scenario(self) -> None:
        event = parse_media_event(
            encoded(
                {
                    "event": "start",
                    "sequenceNumber": "1",
                    "streamSid": "MZ-fake",
                    "start": {
                        "callSid": "CA-fake",
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1,
                        },
                        "customParameters": {
                            "scenario_id": "schedule_appointment_001"
                        },
                    },
                }
            )
        )

        self.assertEqual(event.event, MediaEventType.START)
        self.assertEqual(event.scenario_id, "schedule_appointment_001")
        self.assertEqual(event.call_sid, "CA-fake")

    def test_parses_and_decodes_media_event(self) -> None:
        audio = b"fake mulaw bytes"
        event = parse_media_event(
            encoded(
                {
                    "event": "media",
                    "sequenceNumber": "2",
                    "streamSid": "MZ-fake",
                    "media": {
                        "track": "inbound",
                        "timestamp": "20",
                        "payload": base64.b64encode(audio).decode("ascii"),
                    },
                }
            )
        )

        self.assertEqual(event.audio, audio)
        self.assertEqual(event.media_timestamp_ms, 20)

    def test_parses_mark_event(self) -> None:
        event = parse_media_event(
            encoded(
                {
                    "event": "mark",
                    "sequenceNumber": "3",
                    "streamSid": "MZ-fake",
                    "mark": {"name": "response-1"},
                }
            )
        )

        self.assertEqual(event.mark_name, "response-1")

    def test_parses_stop_event(self) -> None:
        event = parse_media_event(
            encoded(
                {
                    "event": "stop",
                    "sequenceNumber": "4",
                    "streamSid": "MZ-fake",
                    "stop": {"callSid": "CA-fake"},
                }
            )
        )

        self.assertEqual(event.event, MediaEventType.STOP)
        self.assertEqual(event.call_sid, "CA-fake")

    def test_rejects_invalid_base64_audio(self) -> None:
        with self.assertRaises(MediaEventError):
            parse_media_event(
                encoded(
                    {
                        "event": "media",
                        "sequenceNumber": "2",
                        "streamSid": "MZ-fake",
                        "media": {
                            "track": "inbound",
                            "timestamp": "20",
                            "payload": "not-base64!",
                        },
                    }
                )
            )

    def test_rejects_unsupported_audio_format(self) -> None:
        with self.assertRaises(MediaEventError):
            parse_media_event(
                encoded(
                    {
                        "event": "start",
                        "sequenceNumber": "1",
                        "streamSid": "MZ-fake",
                        "start": {
                            "callSid": "CA-fake",
                            "mediaFormat": {
                                "encoding": "audio/wav",
                                "sampleRate": 44100,
                                "channels": 2,
                            },
                            "customParameters": {
                                "scenario_id": "schedule_appointment_001"
                            },
                        },
                    }
                )
            )

    def test_rejects_unknown_scenario(self) -> None:
        with self.assertRaises(ScenarioError):
            parse_media_event(
                encoded(
                    {
                        "event": "start",
                        "sequenceNumber": "1",
                        "streamSid": "MZ-fake",
                        "start": {
                            "callSid": "CA-fake",
                            "mediaFormat": {
                                "encoding": "audio/x-mulaw",
                                "sampleRate": 8000,
                                "channels": 1,
                            },
                            "customParameters": {"scenario_id": "does_not_exist"},
                        },
                    }
                )
            )

    def test_rejects_unknown_event_type(self) -> None:
        with self.assertRaises(MediaEventError):
            parse_media_event(encoded({"event": "mystery"}))


if __name__ == "__main__":
    unittest.main()
