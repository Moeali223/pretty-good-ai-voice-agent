"""Process a completed recording into a transcript and bug report."""

import json
from pathlib import Path

from voice_bot.recordings import RecordingProvider, save_recording
from voice_bot.reports import analyze_transcript, save_bug_report
from voice_bot.runs import CallStatus, update_call_status
from voice_bot.transcription import TranscriptionProvider
from voice_bot.transcripts import save_transcript


def process_completed_call(
    call_directory: Path,
    *,
    recording_provider: RecordingProvider,
    recording_id: str,
    transcription_provider: TranscriptionProvider,
) -> None:
    """Save and analyze one completed call using injected providers."""
    update_call_status(call_directory, CallStatus.PROCESSING)
    try:
        recording_path = call_directory / "recording.mp3"
        if not recording_path.is_file():
            recording_path = save_recording(
                call_directory,
                recording_provider,
                recording_id,
            )
        segments = transcription_provider.transcribe(recording_path)
        save_transcript(call_directory, segments)

        metadata = json.loads(
            (call_directory / "metadata.json").read_text(encoding="utf-8")
        )
        report = analyze_transcript(
            metadata["call_id"], metadata["scenario_id"], segments
        )
        save_bug_report(call_directory, report)
    except Exception:
        update_call_status(call_directory, CallStatus.FAILED)
        raise
    update_call_status(call_directory, CallStatus.REVIEW_READY)
