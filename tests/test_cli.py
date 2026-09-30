"""Tests for the offline command-line tools."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voice_bot.__main__ import main
from voice_bot.config import Configuration
from voice_bot.runs import RunRecordError, attach_completed_recording, create_call_run
from voice_bot.transcripts import Speaker


class OfflineCommandTests(unittest.TestCase):
    def test_list_prints_all_scenarios(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["list"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue().count("\n"), 10)
        self.assertIn("schedule_appointment_001", output.getvalue())
        self.assertIn("no_availability_010", output.getvalue())

    def test_preview_prints_selected_patient_prompt(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["preview", "office_hours_005"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Riley Adams", output.getvalue())
        self.assertIn("office is open after 5:00 PM", output.getvalue())

    @patch("voice_bot.__main__.simulate_call_lifecycle")
    def test_simulate_reports_output_without_real_services(self, simulate) -> None:
        simulate.return_value = Path("output/test-call")
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["simulate", "schedule_appointment_001"])

        self.assertEqual(exit_code, 0)
        simulate.assert_called_once_with("schedule_appointment_001")
        self.assertIn("Offline simulation completed", output.getvalue())
        self.assertIn("output/test-call", output.getvalue())

    def test_process_call_requires_two_different_speaker_labels(self) -> None:
        with self.assertRaises(RunRecordError):
            main(
                [
                    "process-call",
                    "CA-test",
                    "--patient-label",
                    "A",
                    "--agent-label",
                    "A",
                ]
            )

    def test_process_call_builds_verified_provider_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id="CA-process-test",
                output_root=Path(temporary_directory),
            )
            attach_completed_recording(call_directory, "RE-process-test")
            configuration = Configuration(
                twilio_account_sid="AC-test",
                twilio_auth_token="test-token",
                twilio_phone_number=None,
                openai_api_key="test-key",
                public_base_url=None,
                enable_real_calls=False,
            )
            output = io.StringIO()

            with (
                patch("voice_bot.__main__.load_configuration", return_value=configuration),
                patch("voice_bot.__main__.get_call_directory", return_value=call_directory),
                patch("voice_bot.__main__.create_twilio_client", return_value=object()),
                patch("voice_bot.__main__.create_openai_client", return_value=object()),
                patch("voice_bot.__main__.process_completed_call") as process,
                redirect_stdout(output),
            ):
                exit_code = main(
                    [
                        "process-call",
                        "CA-process-test",
                        "--patient-label",
                        "speaker_0",
                        "--agent-label",
                        "speaker_1",
                        "--system-label",
                        "speaker_2",
                    ]
                )

            self.assertEqual(exit_code, 0)
            transcription = process.call_args.kwargs["transcription_provider"]
            self.assertEqual(
                transcription._speaker_map,
                {
                    "speaker_0": Speaker.PATIENT,
                    "speaker_1": Speaker.HEALTHCARE_AGENT,
                    "speaker_2": Speaker.SYSTEM,
                },
            )
            self.assertIn("ready for review", output.getvalue())


if __name__ == "__main__":
    unittest.main()
