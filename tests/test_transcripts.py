"""Tests for timestamped transcript storage."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.runs import create_call_run
from voice_bot.transcripts import (
    Speaker,
    TranscriptError,
    TranscriptSegment,
    save_transcript,
)


class TranscriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.call_directory = create_call_run(
            "schedule_appointment_001",
            call_id="transcript-test-001",
            output_root=Path(self.temporary_directory.name),
        )

    def test_saves_json_and_markdown(self) -> None:
        segments = [
            TranscriptSegment(
                Speaker.SYSTEM,
                start_ms=0,
                end_ms=900,
                text="This call may be recorded.",
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT,
                start_ms=1000,
                end_ms=1800,
                text="How may I help you?",
            ),
            TranscriptSegment(
                Speaker.PATIENT,
                start_ms=2100,
                end_ms=4300,
                text="I'd like to schedule an appointment.",
            ),
        ]

        json_path, markdown_path = save_transcript(self.call_directory, segments)
        transcript = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(transcript["call_id"], "transcript-test-001")
        self.assertEqual(transcript["segments"][0]["speaker"], "system")
        self.assertIn("System", markdown)
        self.assertIn("[00:00:02.100] Patient", markdown)
        self.assertIn("schedule an appointment", markdown)

    def test_allows_overlapping_segments_for_barge_in(self) -> None:
        segments = [
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 1000, 4000, "I can offer Monday morning."
            ),
            TranscriptSegment(
                Speaker.PATIENT, 3000, 4500, "Sorry, mornings won't work."
            ),
        ]

        json_path, _ = save_transcript(self.call_directory, segments)

        self.assertTrue(json_path.exists())

    def test_rejects_empty_transcript(self) -> None:
        with self.assertRaises(TranscriptError):
            save_transcript(self.call_directory, [])

    def test_rejects_invalid_timestamps(self) -> None:
        with self.assertRaises(TranscriptError):
            save_transcript(
                self.call_directory,
                [TranscriptSegment(Speaker.PATIENT, 2000, 1000, "Hello")],
            )

    def test_rejects_out_of_order_segments(self) -> None:
        with self.assertRaises(TranscriptError):
            save_transcript(
                self.call_directory,
                [
                    TranscriptSegment(Speaker.PATIENT, 2000, 3000, "Second"),
                    TranscriptSegment(Speaker.HEALTHCARE_AGENT, 1000, 1500, "First"),
                ],
            )

    def test_requires_call_metadata(self) -> None:
        empty_directory = Path(self.temporary_directory.name) / "missing-metadata"
        empty_directory.mkdir()

        with self.assertRaises(TranscriptError):
            save_transcript(
                empty_directory,
                [TranscriptSegment(Speaker.PATIENT, 0, 1000, "Hello")],
            )


if __name__ == "__main__":
    unittest.main()
