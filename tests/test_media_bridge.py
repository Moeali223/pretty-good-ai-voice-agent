"""Offline integration tests for the media bridge."""

import base64
import json
import unittest

from voice_bot.media_bridge import MediaBridge, MediaBridgeError
from voice_bot.realtime import (
    InMemoryRealtimeSession,
    RealtimeEvent,
    RealtimeEventType,
)


def message(event: dict) -> str:
    return json.dumps(event)


def connected_message() -> str:
    return message({"event": "connected", "protocol": "Call", "version": "1.0.0"})


def start_message() -> str:
    return message(
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


class MediaBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = InMemoryRealtimeSession()
        self.bridge = MediaBridge(self.session)
        await self.bridge.process_twilio_message(connected_message())
        await self.bridge.process_twilio_message(start_message())

    async def test_start_connects_realtime_with_patient_prompt(self) -> None:
        self.assertTrue(self.session.connected)
        self.assertIn("Jamie Carter", self.session.instructions or "")
        self.assertEqual(self.bridge.stream_sid, "MZ-fake")

    async def test_inbound_audio_reaches_fake_realtime_session(self) -> None:
        audio = b"fake caller mulaw"
        await self.bridge.process_twilio_message(
            message(
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

        self.assertEqual(self.session.received_audio, [audio])

    async def test_patient_audio_becomes_media_and_mark_messages(self) -> None:
        output = await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.AUDIO, audio=b"fake patient mulaw")
        )
        media, mark = [json.loads(item) for item in output]

        self.assertEqual(media["event"], "media")
        self.assertEqual(mark["event"], "mark")
        self.assertEqual(mark["mark"]["name"], "response-1")
        self.assertIn("response-1", self.bridge.pending_marks)

    async def test_barge_in_interrupts_and_clears_audio(self) -> None:
        await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.AUDIO, audio=b"fake patient mulaw")
        )

        output = await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.SPEECH_STARTED)
        )

        self.assertEqual(self.session.interruption_count, 1)
        self.assertEqual(json.loads(output[0])["event"], "clear")
        self.assertEqual(self.bridge.pending_marks, set())

    async def test_speech_start_before_patient_response_does_not_cancel(self) -> None:
        output = await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.SPEECH_STARTED)
        )

        self.assertEqual(output, [])
        self.assertEqual(self.session.interruption_count, 0)

    async def test_response_done_prevents_late_cancellation(self) -> None:
        await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.AUDIO, audio=b"fake patient mulaw")
        )
        await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.RESPONSE_DONE)
        )

        output = await self.bridge.process_realtime_event(
            RealtimeEvent(RealtimeEventType.SPEECH_STARTED)
        )

        self.assertEqual(output, [])
        self.assertEqual(self.session.interruption_count, 0)

    async def test_ignores_benign_late_cancellation_error(self) -> None:
        output = await self.bridge.process_realtime_event(
            RealtimeEvent(
                RealtimeEventType.ERROR,
                message="Cancellation failed: no active response found",
            )
        )

        self.assertEqual(output, [])

    async def test_stop_closes_realtime_session(self) -> None:
        await self.bridge.process_twilio_message(
            message(
                {
                    "event": "stop",
                    "sequenceNumber": "3",
                    "streamSid": "MZ-fake",
                    "stop": {"callSid": "CA-fake"},
                }
            )
        )

        self.assertTrue(self.session.closed)
        self.assertFalse(self.bridge.connected)

    async def test_rejects_event_for_different_stream(self) -> None:
        with self.assertRaises(MediaBridgeError):
            await self.bridge.process_twilio_message(
                message(
                    {
                        "event": "mark",
                        "sequenceNumber": "2",
                        "streamSid": "MZ-other",
                        "mark": {"name": "response-1"},
                    }
                )
            )


class MediaBridgeOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_start_before_connected(self) -> None:
        bridge = MediaBridge(InMemoryRealtimeSession())

        with self.assertRaises(MediaBridgeError):
            await bridge.process_twilio_message(start_message())


if __name__ == "__main__":
    unittest.main()
