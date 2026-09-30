"""Tests for the provider-neutral realtime session fake."""

import unittest

from voice_bot.realtime import (
    InMemoryRealtimeSession,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeSessionError,
)


class InMemoryRealtimeSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_connects_with_patient_instructions(self) -> None:
        session = InMemoryRealtimeSession()

        await session.connect("Act as a fictional patient.")

        self.assertTrue(session.connected)
        self.assertEqual(session.instructions, "Act as a fictional patient.")

    async def test_collects_inbound_audio_without_network(self) -> None:
        session = InMemoryRealtimeSession()
        await session.connect("Fictional patient instructions")

        await session.send_audio(b"fake caller audio")

        self.assertEqual(session.received_audio, [b"fake caller audio"])

    async def test_returns_scripted_audio_event(self) -> None:
        session = InMemoryRealtimeSession(
            [RealtimeEvent(RealtimeEventType.AUDIO, audio=b"fake patient audio")]
        )
        await session.connect("Fictional patient instructions")

        event = await session.receive_event()

        self.assertEqual(event.type, RealtimeEventType.AUDIO)
        self.assertEqual(event.audio, b"fake patient audio")

    async def test_records_interruption(self) -> None:
        session = InMemoryRealtimeSession()
        await session.connect("Fictional patient instructions")

        await session.interrupt()

        self.assertEqual(session.interruption_count, 1)

    async def test_rejects_audio_before_connect(self) -> None:
        session = InMemoryRealtimeSession()

        with self.assertRaises(RealtimeSessionError):
            await session.send_audio(b"fake audio")

    async def test_close_is_safe_to_repeat(self) -> None:
        session = InMemoryRealtimeSession()
        await session.connect("Fictional patient instructions")

        await session.close()
        await session.close()

        self.assertTrue(session.closed)
        self.assertFalse(session.connected)


if __name__ == "__main__":
    unittest.main()
