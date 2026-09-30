"""Offline test for completed-call processing."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.post_call import process_completed_call
from voice_bot.recordings import InMemoryRecordingProvider
from voice_bot.runs import CallStatus, create_call_run
from voice_bot.transcription import InMemoryTranscriptionProvider
from voice_bot.transcripts import Speaker, TranscriptSegment


class PostCallTests(unittest.TestCase):
    def test_creates_complete_artifact_set_with_one_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="post-call-001",
                output_root=Path(temporary_directory),
            )
            transcription = InMemoryTranscriptionProvider(
                [
                    TranscriptSegment(
                        Speaker.HEALTHCARE_AGENT, 0, 1000, "How may I help?"
                    ),
                    TranscriptSegment(
                        Speaker.PATIENT, 1200, 2500, "I need an appointment."
                    ),
                ]
            )

            process_completed_call(
                call_directory,
                recording_provider=InMemoryRecordingProvider(b"ID3fake"),
                recording_id="RE-post-call",
                transcription_provider=transcription,
            )

            self.assertEqual(len(transcription.requested_paths), 1)
            for filename in (
                "recording.mp3",
                "transcript.json",
                "transcript.md",
                "bug-report.json",
                "bug-report.md",
            ):
                self.assertTrue((call_directory / filename).exists())
            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["status"], "review_ready")
            self.assertEqual(
                [event["status"] for event in metadata["events"][-2:]],
                ["processing", "review_ready"],
            )

    def test_failed_transcription_can_retry_without_redownloading(self) -> None:
        class FailingTranscription:
            def transcribe(self, recording_path):
                raise RuntimeError("fictional transcription failure")

        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="post-call-retry",
                output_root=Path(temporary_directory),
            )
            recording = InMemoryRecordingProvider(b"ID3fake")

            with self.assertRaises(RuntimeError):
                process_completed_call(
                    call_directory,
                    recording_provider=recording,
                    recording_id="RE-post-call-retry",
                    transcription_provider=FailingTranscription(),
                )

            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["status"], CallStatus.FAILED)

            transcription = InMemoryTranscriptionProvider(
                [
                    TranscriptSegment(
                        Speaker.PATIENT,
                        0,
                        1000,
                        "I need an appointment.",
                    )
                ]
            )
            process_completed_call(
                call_directory,
                recording_provider=recording,
                recording_id="RE-post-call-retry",
                transcription_provider=transcription,
            )

            self.assertEqual(recording.requested_ids, ["RE-post-call-retry"])
            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["status"], CallStatus.REVIEW_READY)


if __name__ == "__main__":
    unittest.main()
