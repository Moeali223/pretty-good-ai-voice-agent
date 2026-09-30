"""OpenAI Realtime WebSocket adapter for 8 kHz G.711 phone audio."""

import base64
import json
import ssl
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from voice_bot.realtime import (
    RealtimeEvent,
    RealtimeEventType,
    RealtimeSessionError,
)


OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime"


class WebSocketConnection(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


WebSocketConnector = Callable[..., Awaitable[WebSocketConnection]]


async def connect_openai_websocket(url: str, **kwargs: Any) -> WebSocketConnection:
    """Open a real socket only when this function is explicitly invoked."""
    import certifi
    from websockets.asyncio.client import connect

    kwargs.setdefault(
        "ssl",
        ssl.create_default_context(cafile=certifi.where()),
    )
    return await connect(url, **kwargs)


class OpenAIRealtimeSession:
    """Translate the project's neutral voice events to OpenAI Realtime events."""

    def __init__(
        self,
        api_key: str,
        *,
        connector: WebSocketConnector,
        url: str = OPENAI_REALTIME_URL,
    ) -> None:
        if not api_key.strip():
            raise RealtimeSessionError("OPENAI_API_KEY is required.")
        self._api_key = api_key
        self._connector = connector
        self._url = url
        self._socket: WebSocketConnection | None = None

    async def connect(self, instructions: str) -> None:
        if self._socket is not None:
            raise RealtimeSessionError("The realtime session is already connected.")
        if not instructions.strip():
            raise RealtimeSessionError("Realtime instructions must not be empty.")
        self._socket = await self._connector(
            self._url,
            additional_headers={"Authorization": f"Bearer {self._api_key}"},
        )
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": instructions,
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcmu"},
                            "turn_detection": {"type": "server_vad"},
                        },
                        "output": {
                            "format": {"type": "audio/pcmu"},
                            "voice": "marin",
                        },
                    },
                },
            }
        )

    async def send_audio(self, audio: bytes) -> None:
        if not audio:
            raise RealtimeSessionError("Realtime audio must be non-empty bytes.")
        await self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(audio).decode("ascii"),
            }
        )

    async def receive_event(self) -> RealtimeEvent:
        socket = self._require_socket()
        while True:
            raw = await socket.recv()
            try:
                event: dict[str, Any] = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as error:
                raise RealtimeSessionError("OpenAI returned invalid JSON.") from error
            event_type = event.get("type")
            if event_type == "response.output_audio.delta":
                try:
                    audio = base64.b64decode(event["delta"], validate=True)
                except Exception as error:
                    raise RealtimeSessionError("OpenAI returned invalid audio.") from error
                return RealtimeEvent(RealtimeEventType.AUDIO, audio=audio)
            if event_type == "input_audio_buffer.speech_started":
                return RealtimeEvent(RealtimeEventType.SPEECH_STARTED)
            if event_type == "input_audio_buffer.speech_stopped":
                return RealtimeEvent(RealtimeEventType.SPEECH_STOPPED)
            if event_type == "response.done":
                return RealtimeEvent(RealtimeEventType.RESPONSE_DONE)
            if event_type == "error":
                error = event.get("error", {})
                return RealtimeEvent(
                    RealtimeEventType.ERROR,
                    message=str(error.get("message", "OpenAI Realtime error")),
                )

    async def interrupt(self) -> None:
        await self._send({"type": "response.cancel"})

    async def close(self) -> None:
        if self._socket is not None:
            await self._socket.close()
            self._socket = None

    async def _send(self, event: dict[str, Any]) -> None:
        await self._require_socket().send(json.dumps(event))

    def _require_socket(self) -> WebSocketConnection:
        if self._socket is None:
            raise RealtimeSessionError("The realtime session is not connected.")
        return self._socket
