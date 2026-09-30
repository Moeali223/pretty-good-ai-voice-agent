"""Tests for local call-run records."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.runs import (
    CallStatus,
    RunRecordError,
    attach_completed_recording,
    create_call_run,
    get_call_directory,
    update_call_status,
)
from voice_bot.scenarios import ScenarioError


class CallRunTests(unittest.TestCase):
    def test_creates_call_directory_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="test-call-001",
                output_root=Path(temporary_directory),
            )
            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )

            self.assertEqual(metadata["call_id"], "test-call-001")
            self.assertEqual(metadata["scenario_id"], "schedule_appointment_001")
            self.assertEqual(metadata["status"], "created")
            self.assertIn("created_at", metadata)
            self.assertEqual(metadata["events"][0]["status"], "created")

    def test_updates_call_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="test-call-002",
                output_root=Path(temporary_directory),
            )

            metadata = update_call_status(call_directory, CallStatus.COMPLETED)

            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(
                [event["status"] for event in metadata["events"]],
                ["created", "completed"],
            )

    def test_attaches_completed_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="recording-callback-001",
                output_root=Path(temporary_directory),
            )

            metadata = attach_completed_recording(
                call_directory,
                "RE-recording-001",
            )

            self.assertEqual(metadata["recording_id"], "RE-recording-001")
            self.assertEqual(metadata["recording_status"], "completed")

    def test_rejects_replacing_attached_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="recording-callback-002",
                output_root=Path(temporary_directory),
            )
            attach_completed_recording(call_directory, "RE-first")

            with self.assertRaises(RunRecordError):
                attach_completed_recording(call_directory, "RE-different")

    def test_rejects_unsafe_call_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(RunRecordError):
                create_call_run(
                    "schedule_appointment_001",
                    call_id="../outside",
                    output_root=Path(temporary_directory),
                )

    def test_rejects_duplicate_call_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_call_run(
                "schedule_appointment_001",
                call_id="duplicate",
                output_root=root,
            )

            with self.assertRaises(RunRecordError):
                create_call_run(
                    "schedule_appointment_001",
                    call_id="duplicate",
                    output_root=root,
                )

    def test_rejects_unknown_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ScenarioError):
                create_call_run(
                    "does_not_exist",
                    output_root=Path(temporary_directory),
                )

    def test_gets_only_existing_safe_call_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            expected = create_call_run(
                "schedule_appointment_001",
                call_id="existing-call",
                output_root=root,
            )

            self.assertEqual(
                get_call_directory("existing-call", output_root=root),
                expected,
            )
            with self.assertRaises(RunRecordError):
                get_call_directory("missing-call", output_root=root)


if __name__ == "__main__":
    unittest.main()
