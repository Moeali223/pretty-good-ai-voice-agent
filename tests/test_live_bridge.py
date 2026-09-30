"""Offline test for concurrent WebSocket bridge orchestration."""

import base64
import asyncio
import json
import unittest

from voice_bot.live_bridge import run_live_media_bridge
from voice_bot.realtime import InMemoryRealtimeSession


class BlockingRealtimeSession(InMemoryRealtimeSession):
    async def receive_event(self):
        await asyncio.Event().wait()


class FakeTwilioSocket:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.sent: list[str] = []

    async def receive_text(self) -> str:
        return self.messages.pop(0)

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


class LiveBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_relays_twilio_audio_then_closes_without_network(self) -> None:
        audio = b"caller audio"
        socket = FakeTwilioSocket(
            [
                {"event": "connected", "protocol": "Call", "version": "1.0.0"},
                {
                    "event": "start",
                    "sequenceNumber": "1",
                    "streamSid": "MZ-test",
                    "start": {
                        "callSid": "CA-test",
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1,
                        },
                        "customParameters": {
                            "scenario_id": "schedule_appointment_001"
                        },
                    },
                },
                {
                    "event": "media",
                    "sequenceNumber": "2",
                    "streamSid": "MZ-test",
                    "media": {
                        "track": "inbound",
                        "timestamp": "20",
                        "payload": base64.b64encode(audio).decode(),
                    },
                },
                {
                    "event": "stop",
                    "sequenceNumber": "3",
                    "streamSid": "MZ-test",
                    "stop": {"callSid": "CA-test"},
                },
            ]
        )
        realtime = BlockingRealtimeSession()

        await run_live_media_bridge(socket, realtime)

        self.assertEqual(realtime.received_audio, [audio])
        self.assertTrue(realtime.closed)


if __name__ == "__main__":
    unittest.main()
