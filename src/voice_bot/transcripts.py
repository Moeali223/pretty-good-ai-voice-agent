"""Validate and save timestamped two-speaker call transcripts."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class TranscriptError(ValueError):
    """Raised when transcript content or call metadata is invalid."""


class Speaker(StrEnum):
    """Voices that may be captured in an assessment recording."""

    PATIENT = "patient"
    HEALTHCARE_AGENT = "healthcare_agent"
    SYSTEM = "system"


@dataclass(frozen=True)
class TranscriptSegment:
    """One timestamped span of speech."""

    speaker: Speaker
    start_ms: int
    end_ms: int
    text: str


def _validate_segments(segments: list[TranscriptSegment]) -> None:
    """Check transcript timing and content while allowing interruptions."""
    if not segments:
        raise TranscriptError("A transcript must contain at least one segment.")

    previous_start = -1
    for position, segment in enumerate(segments, start=1):
        if segment.start_ms < 0 or segment.end_ms <= segment.start_ms:
            raise TranscriptError(f"Segment {position} has invalid timestamps.")
        if segment.start_ms < previous_start:
            raise TranscriptError("Transcript segments must be ordered by start time.")
        if not segment.text.strip():
            raise TranscriptError(f"Segment {position} has empty text.")
        previous_start = segment.start_ms


def _read_call_metadata(call_directory: Path) -> dict[str, Any]:
    """Read the run metadata that identifies this transcript."""
    metadata_path = call_directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TranscriptError(f"Call metadata not found: {metadata_path}.") from error
    except json.JSONDecodeError as error:
        raise TranscriptError(f"Call metadata is invalid: {metadata_path}.") from error

    if not metadata.get("call_id") or not metadata.get("scenario_id"):
        raise TranscriptError("Call metadata is missing its call or scenario ID.")
    return metadata


def _format_timestamp(milliseconds: int) -> str:
    """Format milliseconds as hours:minutes:seconds.milliseconds."""
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def save_transcript(
    call_directory: Path,
    segments: list[TranscriptSegment],
) -> tuple[Path, Path]:
    """Save one validated transcript as JSON and Markdown."""
    _validate_segments(segments)
    metadata = _read_call_metadata(call_directory)

    transcript = {
        "call_id": metadata["call_id"],
        "scenario_id": metadata["scenario_id"],
        "segments": [asdict(segment) for segment in segments],
    }
    json_path = call_directory / "transcript.json"
    json_path.write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")

    markdown_lines = [
        "# Call transcript",
        "",
        f"- Call ID: `{metadata['call_id']}`",
        f"- Scenario ID: `{metadata['scenario_id']}`",
        "",
    ]
    for segment in segments:
        labels = {
            Speaker.PATIENT: "Patient",
            Speaker.HEALTHCARE_AGENT: "Healthcare agent",
            Speaker.SYSTEM: "System",
        }
        label = labels[segment.speaker]
        markdown_lines.append(
            f"**[{_format_timestamp(segment.start_ms)}] {label}:** {segment.text.strip()}"
        )
        markdown_lines.append("")

    markdown_path = call_directory / "transcript.md"
    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")
    return json_path, markdown_path
