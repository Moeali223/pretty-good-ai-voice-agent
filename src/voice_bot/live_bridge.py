"""Run the bidirectional media bridge over two WebSocket connections."""

import asyncio
import json
from typing import Protocol

from voice_bot.media_bridge import MediaBridge
from voice_bot.realtime import RealtimeVoiceSession


class TwilioWebSocket(Protocol):
    async def receive_text(self) -> str: ...
    async def send_text(self, data: str) -> None: ...


async def run_live_media_bridge(
    twilio_socket: TwilioWebSocket,
    realtime_session: RealtimeVoiceSession,
) -> None:
    """Relay messages until either provider closes its side of the call."""
    bridge = MediaBridge(realtime_session)
    realtime_ready = asyncio.Event()

    async def receive_twilio() -> None:
        while True:
            raw = await twilio_socket.receive_text()
            for outgoing in await bridge.process_twilio_message(raw):
                await twilio_socket.send_text(outgoing)
            event_type = json.loads(raw).get("event")
            if event_type == "start":
                realtime_ready.set()
            if event_type == "stop":
                return

    async def receive_realtime() -> None:
        await realtime_ready.wait()
        while True:
            event = await realtime_session.receive_event()
            for outgoing in await bridge.process_realtime_event(event):
                await twilio_socket.send_text(outgoing)

    twilio_task = asyncio.create_task(receive_twilio())
    realtime_task = asyncio.create_task(receive_realtime())
    done, pending = await asyncio.wait(
        {twilio_task, realtime_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()
    await realtime_session.close()
