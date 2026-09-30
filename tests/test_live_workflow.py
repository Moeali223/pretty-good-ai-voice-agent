"""Offline integration test for the guarded live-call artifact workflow."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from voice_bot.post_call import process_completed_call
from voice_bot.recordings import InMemoryRecordingProvider
from voice_bot.runs import create_call_run
from voice_bot.server import app
from voice_bot.transcription import InMemoryTranscriptionProvider
from voice_bot.transcripts import Speaker, TranscriptSegment


class LiveWorkflowTests(unittest.TestCase):
    def test_callbacks_then_processing_create_review_ready_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            call_id = "CA-workflow-001"
            call_directory = create_call_run(
                "schedule_appointment_001",
                call_id=call_id,
                output_root=output_root,
            )
            token = "fictional-workflow-token"
            base_url = "https://assessment.example.test"
            validator = RequestValidator(token)

            with (
                patch.dict(
                    "os.environ",
                    {
                        "ENABLE_REAL_CALLS": "true",
                        "TWILIO_AUTH_TOKEN": token,
                        "PUBLIC_BASE_URL": base_url,
                    },
                    clear=True,
                ),
                patch("voice_bot.server.DEFAULT_OUTPUT_ROOT", output_root),
            ):
                client = TestClient(app)
                status = {"CallSid": call_id, "CallStatus": "completed"}
                response = client.post(
                    "/twilio/call-status",
                    data=status,
                    headers={
                        "X-Twilio-Signature": validator.compute_signature(
                            f"{base_url}/twilio/call-status",
                            status,
                        )
                    },
                )
                self.assertEqual(response.status_code, 204)

                recording = {
                    "CallSid": call_id,
                    "RecordingSid": "RE-workflow-001",
                    "RecordingStatus": "completed",
                }
                response = client.post(
                    "/twilio/recording-status",
                    data=recording,
                    headers={
                        "X-Twilio-Signature": validator.compute_signature(
                            f"{base_url}/twilio/recording-status",
                            recording,
                        )
                    },
                )
                self.assertEqual(response.status_code, 204)

            process_completed_call(
                call_directory,
                recording_provider=InMemoryRecordingProvider(b"ID3fictional"),
                recording_id="RE-workflow-001",
                transcription_provider=InMemoryTranscriptionProvider(
                    [
                        TranscriptSegment(
                            Speaker.HEALTHCARE_AGENT,
                            0,
                            900,
                            "How may I help?",
                        ),
                        TranscriptSegment(
                            Speaker.PATIENT,
                            1000,
                            2000,
                            "I need an appointment.",
                        ),
                    ]
                ),
            )

            metadata = json.loads(
                (call_directory / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["recording_id"], "RE-workflow-001")
            self.assertEqual(metadata["status"], "review_ready")
            self.assertTrue((call_directory / "recording.mp3").is_file())
            self.assertTrue((call_directory / "transcript.json").is_file())
            self.assertTrue((call_directory / "bug-report.md").is_file())


if __name__ == "__main__":
    unittest.main()
