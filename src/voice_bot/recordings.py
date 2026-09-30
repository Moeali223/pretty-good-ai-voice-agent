"""Save MP3 call recordings obtained through an injected provider."""

import json
import re
from pathlib import Path
from typing import Any, Callable, Protocol


SAFE_RECORDING_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class RecordingError(ValueError):
    """Raised when recording data or its destination is unsafe."""


class RecordingProvider(Protocol):
    """Provider interface implemented by an offline fake and Twilio."""

    def download_mp3(self, recording_id: str) -> bytes:
        """Return an MP3 recording for one provider recording ID."""


class InMemoryRecordingProvider:
    """Return fictional MP3 bytes without making a network request."""

    def __init__(self, content: bytes) -> None:
        self._content = content
        self.requested_ids: list[str] = []

    def download_mp3(self, recording_id: str) -> bytes:
        """Record the request and return the configured bytes."""
        self.requested_ids.append(recording_id)
        return self._content


class TwilioRecordingProvider:
    """Download completed MP3 recordings through an authenticated Twilio client."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        *,
        requester: Callable[..., Any] | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        if requester is None:
            from requests import get

            requester = get
        self._requester = requester

    def download_mp3(self, recording_id: str) -> bytes:
        uri = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/"
            f"Recordings/{recording_id}.mp3"
        )
        response = self._requester(
            uri,
            auth=(self._account_sid, self._auth_token),
            timeout=30,
        )
        if getattr(response, "status_code", None) != 200:
            raise RecordingError(
                "Twilio recording download failed with status "
                f"{getattr(response, 'status_code', 'unknown')}."
            )
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            raise RecordingError("Twilio did not return recording bytes.")
        return content


def _looks_like_mp3(content: bytes) -> bool:
    """Recognize an ID3 header or MPEG audio frame sync marker."""
    return content.startswith(b"ID3") or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    )


def save_recording(
    call_directory: Path,
    provider: RecordingProvider,
    recording_id: str,
) -> Path:
    """Fetch one provider recording and save it as recording.mp3."""
    if not SAFE_RECORDING_ID.fullmatch(recording_id):
        raise RecordingError(
            "Recording IDs may contain only letters, numbers, underscores, and hyphens."
        )

    metadata_path = call_directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RecordingError(f"Call metadata not found: {metadata_path}.") from error
    except json.JSONDecodeError as error:
        raise RecordingError(f"Call metadata is invalid: {metadata_path}.") from error
    if not metadata.get("call_id"):
        raise RecordingError("Call metadata is missing its call ID.")

    recording_path = call_directory / "recording.mp3"
    if recording_path.exists():
        raise RecordingError("A recording already exists for this call run.")

    content = provider.download_mp3(recording_id)
    if not isinstance(content, bytes) or not _looks_like_mp3(content):
        raise RecordingError("The provider response is not recognizable MP3 data.")

    recording_path.write_bytes(content)
    return recording_path
