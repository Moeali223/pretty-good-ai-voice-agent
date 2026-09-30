"""Tests for the offline call lifecycle simulation."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.simulation import simulate_call_lifecycle


class CallLifecycleSimulationTests(unittest.TestCase):
    def test_simulates_successful_call_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = simulate_call_lifecycle(
                "schedule_appointment_001",
                call_id="simulated-call-001",
                output_root=Path(temporary_directory),
            )
            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )

            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(
                [event["status"] for event in metadata["events"]],
                ["created", "queued", "ringing", "answered", "completed"],
            )
            self.assertTrue(
                all("timestamp" in event for event in metadata["events"])
            )
            self.assertTrue((call_directory / "transcript.json").exists())
            self.assertTrue((call_directory / "transcript.md").exists())
            self.assertTrue((call_directory / "recording.mp3").exists())
            self.assertTrue((call_directory / "bug-report.json").exists())
            self.assertTrue((call_directory / "bug-report.md").exists())

            report = json.loads(
                (call_directory / "bug-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["call_id"], "simulated-call-001")
            self.assertEqual(report["findings"], [])


if __name__ == "__main__":
    unittest.main()
