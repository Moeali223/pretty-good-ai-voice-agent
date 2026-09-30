"""Tests for the local web application."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from twilio.request_validator import RequestValidator

from voice_bot.server import (
    CallStatus,
    SimulatedAnswerRequest,
    SimulatedCallStatusEvent,
    app,
    health,
    simulated_call_status,
    simulated_twilio_answer,
)
from voice_bot.runs import create_call_run


class ServerTests(unittest.TestCase):
    def test_health_response(self) -> None:
        self.assertEqual(health(), {"status": "ok"})

    def test_health_route_is_registered(self) -> None:
        health_routes = [route for route in app.routes if route.path == "/health"]

        self.assertEqual(len(health_routes), 1)
        self.assertIn("GET", health_routes[0].methods)

    def test_accepts_simulated_call_status(self) -> None:
        event = SimulatedCallStatusEvent(
            call_id="test-call-001",
            scenario_id="schedule_appointment_001",
            status=CallStatus.RINGING,
        )

        response = simulated_call_status(event)

        self.assertTrue(response.accepted)
        self.assertEqual(response.call_id, "test-call-001")
        self.assertEqual(response.status, CallStatus.RINGING)

    def test_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValidationError):
            SimulatedCallStatusEvent(
                call_id="test-call-001",
                scenario_id="schedule_appointment_001",
                status="mystery",
            )

    def test_rejects_unknown_scenario(self) -> None:
        event = SimulatedCallStatusEvent(
            call_id="test-call-001",
            scenario_id="does_not_exist",
            status=CallStatus.QUEUED,
        )

        with self.assertRaises(HTTPException) as context:
            simulated_call_status(event)

        self.assertEqual(context.exception.status_code, 404)

    def test_simulated_status_route_is_registered(self) -> None:
        status_routes = [
            route for route in app.routes if route.path == "/test/call-status"
        ]

        self.assertEqual(len(status_routes), 1)
        self.assertIn("POST", status_routes[0].methods)

    def test_simulated_answer_returns_xml(self) -> None:
        response = simulated_twilio_answer(
            SimulatedAnswerRequest(
                scenario_id="schedule_appointment_001",
                public_base_url="https://assessment.example.test",
            )
        )

        self.assertEqual(response.media_type, "application/xml")
        self.assertIn(b"<Connect>", response.body)
        self.assertIn(b"wss://assessment.example.test/twilio/media", response.body)

    def test_simulated_answer_route_is_registered(self) -> None:
        answer_routes = [
            route for route in app.routes if route.path == "/test/twilio/answer"
        ]

        self.assertEqual(len(answer_routes), 1)
        self.assertIn("POST", answer_routes[0].methods)

    @patch.dict(
        "os.environ",
        {
            "ENABLE_REAL_CALLS": "true",
            "TWILIO_AUTH_TOKEN": "fictional-test-token",
            "PUBLIC_BASE_URL": "https://assessment.example.test",
        },
        clear=True,
    )
    def test_live_answer_rejects_invalid_twilio_signature(self) -> None:
        response = TestClient(app).get(
            "/twilio/answer?scenario_id=schedule_appointment_001",
            headers={"X-Twilio-Signature": "invalid"},
        )

        self.assertEqual(response.status_code, 403)

    def test_signed_live_status_updates_call_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            call_id = "CA-test-status"
            create_call_run(
                "schedule_appointment_001",
                call_id=call_id,
                output_root=output_root,
            )
            public_url = "https://assessment.example.test/twilio/call-status"
            parameters = {"CallSid": call_id, "CallStatus": "in-progress"}
            signature = RequestValidator("fictional-test-token").compute_signature(
                public_url,
                parameters,
            )

            with (
                patch.dict(
                    "os.environ",
                    {
                        "ENABLE_REAL_CALLS": "true",
                        "TWILIO_AUTH_TOKEN": "fictional-test-token",
                        "PUBLIC_BASE_URL": "https://assessment.example.test",
                    },
                    clear=True,
                ),
                patch("voice_bot.server.DEFAULT_OUTPUT_ROOT", output_root),
            ):
                response = TestClient(app).post(
                    "/twilio/call-status",
                    data=parameters,
                    headers={"X-Twilio-Signature": signature},
                )

            self.assertEqual(response.status_code, 204)
            metadata = (output_root / call_id / "metadata.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"status": "answered"', metadata)

    @patch.dict(
        "os.environ",
        {
            "ENABLE_REAL_CALLS": "true",
            "TWILIO_AUTH_TOKEN": "fictional-test-token",
            "PUBLIC_BASE_URL": "https://assessment.example.test",
        },
        clear=True,
    )
    def test_live_status_rejects_invalid_twilio_signature(self) -> None:
        response = TestClient(app).post(
            "/twilio/call-status",
            data={"CallSid": "CA-test", "CallStatus": "ringing"},
            headers={"X-Twilio-Signature": "invalid"},
        )

        self.assertEqual(response.status_code, 403)

    def test_signed_recording_status_attaches_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            call_id = "CA-test-recording"
            create_call_run(
                "schedule_appointment_001",
                call_id=call_id,
                output_root=output_root,
            )
            public_url = "https://assessment.example.test/twilio/recording-status"
            parameters = {
                "CallSid": call_id,
                "RecordingSid": "RE-test-recording",
                "RecordingStatus": "completed",
            }
            signature = RequestValidator("fictional-test-token").compute_signature(
                public_url,
                parameters,
            )

            with (
                patch.dict(
                    "os.environ",
                    {
                        "ENABLE_REAL_CALLS": "true",
                        "TWILIO_AUTH_TOKEN": "fictional-test-token",
                        "PUBLIC_BASE_URL": "https://assessment.example.test",
                    },
                    clear=True,
                ),
                patch("voice_bot.server.DEFAULT_OUTPUT_ROOT", output_root),
            ):
                response = TestClient(app).post(
                    "/twilio/recording-status",
                    data=parameters,
                    headers={"X-Twilio-Signature": signature},
                )

            self.assertEqual(response.status_code, 204)
            metadata = (output_root / call_id / "metadata.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"recording_id": "RE-test-recording"', metadata)


if __name__ == "__main__":
    unittest.main()
