"""Run a complete fake call pipeline without telephone or AI services."""

from pathlib import Path

from voice_bot.recordings import InMemoryRecordingProvider, save_recording
from voice_bot.reports import analyze_transcript, save_bug_report
from voice_bot.runs import CallStatus, create_call_run, update_call_status
from voice_bot.scenarios import get_scenario
from voice_bot.transcription import InMemoryTranscriptionProvider, transcribe_recording
from voice_bot.transcripts import Speaker, TranscriptSegment


SIMULATED_STATUS_SEQUENCE = (
    CallStatus.QUEUED,
    CallStatus.RINGING,
    CallStatus.ANSWERED,
)
SIMULATED_RECORDING_ID = "offline-recording"
SIMULATED_MP3 = b"ID3" + b"fictional offline call audio"


def _fictional_transcript(scenario_id: str) -> list[TranscriptSegment]:
    """Create a short clean dialogue for offline pipeline testing."""
    scenario = get_scenario(scenario_id)
    return [
        TranscriptSegment(
            speaker=Speaker.HEALTHCARE_AGENT,
            start_ms=0,
            end_ms=1_500,
            text="Thank you for calling. How may I help you today?",
        ),
        TranscriptSegment(
            speaker=Speaker.PATIENT,
            start_ms=1_800,
            end_ms=4_500,
            text=scenario["goal"],
        ),
        TranscriptSegment(
            speaker=Speaker.HEALTHCARE_AGENT,
            start_ms=4_800,
            end_ms=7_000,
            text="I understand. Let me help you with that request.",
        ),
    ]


def simulate_call_lifecycle(
    scenario_id: str,
    *,
    call_id: str | None = None,
    output_root: Path | None = None,
) -> Path:
    """Create a run and move it through a successful fake lifecycle."""
    call_directory = create_call_run(
        scenario_id,
        call_id=call_id,
        output_root=output_root,
    )

    for status in SIMULATED_STATUS_SEQUENCE:
        update_call_status(call_directory, status)

    recording_provider = InMemoryRecordingProvider(SIMULATED_MP3)
    save_recording(call_directory, recording_provider, SIMULATED_RECORDING_ID)

    segments = _fictional_transcript(scenario_id)
    transcription_provider = InMemoryTranscriptionProvider(segments)
    transcribe_recording(call_directory, transcription_provider)
    report = analyze_transcript(call_directory.name, scenario_id, segments)
    save_bug_report(call_directory, report)
    update_call_status(call_directory, CallStatus.COMPLETED)

    return call_directory
