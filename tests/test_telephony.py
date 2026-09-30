"""Tests for provider-neutral outbound call preparation."""

import unittest
from typing import Any

from voice_bot.config import Configuration
from voice_bot.safety import (
    APPROVED_PHONE_NUMBER,
    REAL_CALL_CONFIRMATION,
    CallNotAuthorizedError,
)
from voice_bot.telephony import (
    TelephonyConfigurationError,
    TwilioCallProvider,
    create_assessment_call,
)


class FakeCallProvider:
    """Records a request in memory and never contacts a telephone service."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def create_call(self, **parameters: Any) -> str:
        self.requests.append(parameters)
        return "fake-provider-call-001"


def configuration(
    *,
    enabled: bool = True,
    phone_number: str | None = "+15551234567",
    public_url: str | None = "https://assessment.example.test",
) -> Configuration:
    """Build non-secret test configuration."""
    return Configuration(
        twilio_account_sid=None,
        twilio_auth_token=None,
        twilio_phone_number=phone_number,
        openai_api_key=None,
        public_base_url=public_url,
        enable_real_calls=enabled,
    )


class AssessmentCallTests(unittest.TestCase):
    def test_twilio_adapter_returns_call_sid(self) -> None:
        class Calls:
            def create(self, **parameters):
                self.parameters = parameters
                return type("Call", (), {"sid": "CA-real-shape"})()

        client = type("Client", (), {"calls": Calls()})()
        provider = TwilioCallProvider(client)

        self.assertEqual(provider.create_call(to="+18054398008"), "CA-real-shape")

    def test_fake_provider_receives_safe_recorded_call_request(self) -> None:
        provider = FakeCallProvider()

        prepared = create_assessment_call(
            provider,
            configuration(),
            scenario_id="schedule_appointment_001",
            confirmation=REAL_CALL_CONFIRMATION,
        )

        self.assertEqual(prepared.destination, APPROVED_PHONE_NUMBER)
        self.assertEqual(prepared.provider_call_id, "fake-provider-call-001")
        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(request["to"], APPROVED_PHONE_NUMBER)
        self.assertTrue(request["record"])
        self.assertIn("scenario_id=schedule_appointment_001", request["url"])
        self.assertEqual(request["recording_channels"], "dual")
        self.assertEqual(request["recording_track"], "both")

    def test_disabled_calls_never_reach_provider(self) -> None:
        provider = FakeCallProvider()

        with self.assertRaises(CallNotAuthorizedError):
            create_assessment_call(
                provider,
                configuration(enabled=False),
                scenario_id="schedule_appointment_001",
                confirmation=REAL_CALL_CONFIRMATION,
            )

        self.assertEqual(provider.requests, [])

    def test_wrong_confirmation_never_reaches_provider(self) -> None:
        provider = FakeCallProvider()

        with self.assertRaises(CallNotAuthorizedError):
            create_assessment_call(
                provider,
                configuration(),
                scenario_id="schedule_appointment_001",
                confirmation="yes",
            )

        self.assertEqual(provider.requests, [])

    def test_missing_source_number_never_reaches_provider(self) -> None:
        provider = FakeCallProvider()

        with self.assertRaises(TelephonyConfigurationError):
            create_assessment_call(
                provider,
                configuration(phone_number=None),
                scenario_id="schedule_appointment_001",
                confirmation=REAL_CALL_CONFIRMATION,
            )

        self.assertEqual(provider.requests, [])

    def test_non_https_public_url_never_reaches_provider(self) -> None:
        provider = FakeCallProvider()

        with self.assertRaises(TelephonyConfigurationError):
            create_assessment_call(
                provider,
                configuration(public_url="http://localhost:8000"),
                scenario_id="schedule_appointment_001",
                confirmation=REAL_CALL_CONFIRMATION,
            )

        self.assertEqual(provider.requests, [])


if __name__ == "__main__":
    unittest.main()
