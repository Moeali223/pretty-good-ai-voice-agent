"""Offline tests for Twilio webhook signature validation."""

import unittest

from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator

from voice_bot.twilio_security import (
    TwilioRequestValidationError,
    public_request_url,
    validate_twilio_signature,
)


AUTH_TOKEN = "fictional-test-auth-token"


class TwilioSecurityTests(unittest.TestCase):
    def test_accepts_valid_http_signature(self) -> None:
        url = "https://assessment.example.test/twilio/call-status"
        parameters = FormData(
            [("CallSid", "CA-test"), ("CallStatus", "completed")]
        )
        signature = RequestValidator(AUTH_TOKEN).compute_signature(url, parameters)

        validate_twilio_signature(
            auth_token=AUTH_TOKEN,
            signature=signature,
            url=url,
            parameters=parameters,
        )

    def test_rejects_modified_parameters(self) -> None:
        url = "https://assessment.example.test/twilio/call-status"
        signed = {"CallSid": "CA-test", "CallStatus": "completed"}
        signature = RequestValidator(AUTH_TOKEN).compute_signature(url, signed)

        with self.assertRaises(TwilioRequestValidationError):
            validate_twilio_signature(
                auth_token=AUTH_TOKEN,
                signature=signature,
                url=url,
                parameters={"CallSid": "CA-other", "CallStatus": "completed"},
            )

    def test_rejects_missing_signature(self) -> None:
        with self.assertRaises(TwilioRequestValidationError):
            validate_twilio_signature(
                auth_token=AUTH_TOKEN,
                signature=None,
                url="https://assessment.example.test/twilio/answer",
            )

    def test_accepts_websocket_trailing_slash_variant(self) -> None:
        signed_url = "wss://assessment.example.test/twilio/media/"
        signature = RequestValidator(AUTH_TOKEN).compute_signature(signed_url, {})

        validate_twilio_signature(
            auth_token=AUTH_TOKEN,
            signature=signature,
            url="wss://assessment.example.test/twilio/media",
            allow_trailing_slash=True,
        )

    def test_rebuilds_public_urls_instead_of_proxy_urls(self) -> None:
        self.assertEqual(
            public_request_url(
                "https://assessment.example.test",
                "/twilio/answer",
                "scenario_id=schedule_appointment_001",
            ),
            "https://assessment.example.test/twilio/answer?scenario_id=schedule_appointment_001",
        )
        self.assertEqual(
            public_request_url(
                "https://assessment.example.test",
                "/twilio/media",
                websocket=True,
            ),
            "wss://assessment.example.test/twilio/media",
        )


if __name__ == "__main__":
    unittest.main()
