"""Create and update local records for simulated or live call runs."""

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from voice_bot.scenarios import get_scenario


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"
SAFE_CALL_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SAFE_RECORDING_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class CallStatus(StrEnum):
    """Lifecycle states stored in a call-run record."""

    CREATED = "created"
    QUEUED = "queued"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    PROCESSING = "processing"
    REVIEW_READY = "review_ready"
    FAILED = "failed"


class RunRecordError(ValueError):
    """Raised when a call-run record is invalid or unavailable."""


def _utc_timestamp() -> str:
    """Return a readable UTC timestamp."""
    return datetime.now(UTC).isoformat()


def _validate_call_id(call_id: str) -> None:
    """Prevent invalid IDs and directory traversal in output paths."""
    if not SAFE_CALL_ID.fullmatch(call_id):
        raise RunRecordError(
            "Call IDs may contain only letters, numbers, underscores, and hyphens."
        )


def get_call_directory(
    call_id: str,
    *,
    output_root: Path | None = None,
) -> Path:
    """Return an existing safe call directory."""
    _validate_call_id(call_id)
    call_directory = (output_root or DEFAULT_OUTPUT_ROOT) / call_id
    if not (call_directory / "metadata.json").is_file():
        raise RunRecordError(f"Call run not found: {call_id}.")
    return call_directory


def create_call_run(
    scenario_id: str,
    *,
    call_id: str | None = None,
    output_root: Path | None = None,
) -> Path:
    """Create a call directory and its initial metadata file."""
    get_scenario(scenario_id)
    resolved_call_id = call_id or f"call-{uuid4().hex}"
    _validate_call_id(resolved_call_id)

    root = output_root or DEFAULT_OUTPUT_ROOT
    call_directory = root / resolved_call_id
    try:
        call_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise RunRecordError(f"Call run already exists: {resolved_call_id}.") from error

    timestamp = _utc_timestamp()
    metadata = {
        "call_id": resolved_call_id,
        "scenario_id": scenario_id,
        "status": CallStatus.CREATED,
        "created_at": timestamp,
        "updated_at": timestamp,
        "events": [
            {
                "status": CallStatus.CREATED,
                "timestamp": timestamp,
            }
        ],
    }
    _write_metadata(call_directory, metadata)
    return call_directory


def update_call_status(call_directory: Path, status: CallStatus) -> dict[str, Any]:
    """Update the lifecycle status in an existing call-run record."""
    metadata_path = call_directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RunRecordError(f"Call metadata not found: {metadata_path}.") from error
    except json.JSONDecodeError as error:
        raise RunRecordError(f"Call metadata is invalid: {metadata_path}.") from error

    timestamp = _utc_timestamp()
    metadata["status"] = status
    metadata["updated_at"] = timestamp
    metadata.setdefault("events", []).append(
        {
            "status": status,
            "timestamp": timestamp,
        }
    )
    _write_metadata(call_directory, metadata)
    return metadata


def attach_completed_recording(
    call_directory: Path,
    recording_id: str,
) -> dict[str, Any]:
    """Store the safe provider ID for a completed call recording."""
    if not SAFE_RECORDING_ID.fullmatch(recording_id):
        raise RunRecordError(
            "Recording IDs may contain only letters, numbers, underscores, and hyphens."
        )

    metadata_path = call_directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RunRecordError(f"Call metadata not found: {metadata_path}.") from error
    except json.JSONDecodeError as error:
        raise RunRecordError(f"Call metadata is invalid: {metadata_path}.") from error

    existing_recording_id = metadata.get("recording_id")
    if existing_recording_id and existing_recording_id != recording_id:
        raise RunRecordError("A different recording is already attached to this call.")

    metadata["recording_id"] = recording_id
    metadata["recording_status"] = "completed"
    metadata["updated_at"] = _utc_timestamp()
    _write_metadata(call_directory, metadata)
    return metadata


def _write_metadata(call_directory: Path, metadata: dict[str, Any]) -> None:
    """Write formatted metadata without storing credentials."""
    metadata_path = call_directory / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
