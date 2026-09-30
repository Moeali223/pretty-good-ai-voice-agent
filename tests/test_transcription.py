"""Tests for provider-neutral, offline call transcription."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.runs import create_call_run
from voice_bot.transcription import (
    InMemoryTranscriptionProvider,
    OpenAITranscriptionProvider,
    TranscriptionError,
    transcribe_recording,
)
from voice_bot.transcripts import Speaker, TranscriptError, TranscriptSegment


class TranscriptionTests(unittest.TestCase):
    def test_openai_adapter_maps_diarized_speakers_and_seconds(self) -> None:
        class Transcriptions:
            def create(self, **parameters):
                self.parameters = parameters
                return type(
                    "Result",
                    (),
                    {
                        "segments": [
                            {"speaker": "A", "start": 0.0, "end": 1.2, "text": "Hello"},
                            {"speaker": "B", "start": 1.5, "end": 2.7, "text": "Hi"},
                        ]
                    },
                )()

        transcriptions = Transcriptions()
        client = type(
            "Client",
            (),
            {"audio": type("Audio", (), {"transcriptions": transcriptions})()},
        )()
        provider = OpenAITranscriptionProvider(
            client,
            speaker_map={"A": Speaker.HEALTHCARE_AGENT, "B": Speaker.PATIENT},
        )

        segments = provider.transcribe(self.recording_path)

        self.assertEqual(segments[0].end_ms, 1200)
        self.assertEqual(segments[1].speaker, Speaker.PATIENT)
        self.assertEqual(transcriptions.parameters["response_format"], "diarized_json")

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.call_directory = create_call_run(
            "schedule_appointment_001",
            call_id="transcription-test-001",
            output_root=Path(self.temporary_directory.name),
        )
        self.recording_path = self.call_directory / "recording.mp3"
        self.recording_path.write_bytes(b"ID3fictional audio")
        self.segments = [
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 0, 1200, "How may I help you?"
            ),
            TranscriptSegment(
                Speaker.PATIENT, 1500, 3600, "I need to schedule an appointment."
            ),
        ]

    def test_fake_provider_creates_two_transcript_files(self) -> None:
        provider = InMemoryTranscriptionProvider(self.segments)

        json_path, markdown_path = transcribe_recording(
            self.call_directory, provider
        )

        transcript = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(provider.requested_paths, [self.recording_path])
        self.assertEqual(len(transcript["segments"]), 2)
        self.assertEqual(transcript["segments"][1]["speaker"], "patient")
        self.assertIn("Healthcare agent", markdown_path.read_text(encoding="utf-8"))

    def test_missing_recording_is_rejected_before_provider_call(self) -> None:
        self.recording_path.unlink()
        provider = InMemoryTranscriptionProvider(self.segments)

        with self.assertRaises(TranscriptionError):
            transcribe_recording(self.call_directory, provider)

        self.assertEqual(provider.requested_paths, [])

    def test_empty_provider_result_is_rejected(self) -> None:
        provider = InMemoryTranscriptionProvider([])

        with self.assertRaises(TranscriptError):
            transcribe_recording(self.call_directory, provider)

    def test_fake_returns_a_new_list_for_each_request(self) -> None:
        provider = InMemoryTranscriptionProvider(self.segments)

        first = provider.transcribe(self.recording_path)
        first.clear()

        self.assertEqual(provider.transcribe(self.recording_path), self.segments)


if __name__ == "__main__":
    unittest.main()
