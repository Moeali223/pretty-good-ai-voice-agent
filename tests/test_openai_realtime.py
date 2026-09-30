"""Offline tests for OpenAI Realtime event translation."""

import base64
import json
import ssl
import unittest
from unittest.mock import AsyncMock, patch

from voice_bot.openai_realtime import OpenAIRealtimeSession, connect_openai_websocket
from voice_bot.realtime import RealtimeEventType


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.received: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        return self.received.pop(0)

    async def close(self) -> None:
        self.closed = True


class OpenAIRealtimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.socket = FakeSocket()
        self.connection_requests: list[tuple[str, dict]] = []

        async def connect(url: str, **kwargs):
            self.connection_requests.append((url, kwargs))
            return self.socket

        self.session = OpenAIRealtimeSession("test-key", connector=connect)
        await self.session.connect("Act as fictional patient Jamie.")

    async def test_connect_configures_pcmu_audio_and_instructions(self) -> None:
        update = self.socket.sent[0]
        self.assertEqual(update["type"], "session.update")
        self.assertEqual(
            update["session"]["audio"]["input"]["format"]["type"],
            "audio/pcmu",
        )
        self.assertIn("Jamie", update["session"]["instructions"])
        self.assertEqual(
            self.connection_requests[0][1]["additional_headers"]["Authorization"],
            "Bearer test-key",
        )

    async def test_sends_base64_audio(self) -> None:
        await self.session.send_audio(b"phone audio")
        event = self.socket.sent[-1]
        self.assertEqual(event["type"], "input_audio_buffer.append")
        self.assertEqual(base64.b64decode(event["audio"]), b"phone audio")

    async def test_receives_audio_and_speech_events(self) -> None:
        self.socket.received.extend(
            [
                json.dumps(
                    {
                        "type": "response.output_audio.delta",
                        "delta": base64.b64encode(b"patient audio").decode(),
                    }
                ),
                json.dumps({"type": "input_audio_buffer.speech_started"}),
            ]
        )
        audio = await self.session.receive_event()
        speech = await self.session.receive_event()
        self.assertEqual(audio.audio, b"patient audio")
        self.assertEqual(speech.type, RealtimeEventType.SPEECH_STARTED)

    async def test_interrupt_and_close(self) -> None:
        await self.session.interrupt()
        await self.session.close()
        self.assertEqual(self.socket.sent[-1]["type"], "response.cancel")
        self.assertTrue(self.socket.closed)


class OpenAIConnectorTests(unittest.IsolatedAsyncioTestCase):
    @patch("websockets.asyncio.client.connect", new_callable=AsyncMock)
    async def test_uses_certifi_for_tls_validation(self, connect: AsyncMock) -> None:
        connect.return_value = FakeSocket()

        await connect_openai_websocket(
            "wss://api.openai.com/v1/realtime",
            additional_headers={"Authorization": "Bearer test-key"},
        )

        tls_context = connect.call_args.kwargs["ssl"]
        self.assertIsInstance(tls_context, ssl.SSLContext)
        self.assertEqual(tls_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(tls_context.check_hostname)


if __name__ == "__main__":
    unittest.main()
