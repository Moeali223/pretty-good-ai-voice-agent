"""Tests for the outbound-call destination guard."""

import unittest

from voice_bot.safety import (
    APPROVED_PHONE_NUMBER,
    REAL_CALL_CONFIRMATION,
    CallNotAuthorizedError,
    DestinationNotAllowedError,
    authorize_real_call,
    require_approved_destination,
)


class DestinationSafetyTests(unittest.TestCase):
    def test_accepts_approved_number(self) -> None:
        self.assertEqual(
            require_approved_destination("+1-805-439-8008"),
            APPROVED_PHONE_NUMBER,
        )

    def test_accepts_approved_number_without_punctuation(self) -> None:
        self.assertEqual(
            require_approved_destination("8054398008"),
            APPROVED_PHONE_NUMBER,
        )

    def test_rejects_different_number(self) -> None:
        with self.assertRaises(DestinationNotAllowedError):
            require_approved_destination("+1-805-439-8009")

    def test_rejects_missing_number(self) -> None:
        with self.assertRaises(DestinationNotAllowedError):
            require_approved_destination("")

    def test_rejects_malformed_number(self) -> None:
        with self.assertRaises(DestinationNotAllowedError):
            require_approved_destination("not a phone number")

    def test_authorizes_call_when_every_check_passes(self) -> None:
        destination = authorize_real_call(
            APPROVED_PHONE_NUMBER,
            real_calls_enabled=True,
            confirmation=REAL_CALL_CONFIRMATION,
        )

        self.assertEqual(destination, APPROVED_PHONE_NUMBER)

    def test_call_authorization_rejects_disabled_calls(self) -> None:
        with self.assertRaises(CallNotAuthorizedError):
            authorize_real_call(
                APPROVED_PHONE_NUMBER,
                real_calls_enabled=False,
                confirmation=REAL_CALL_CONFIRMATION,
            )

    def test_call_authorization_rejects_wrong_confirmation(self) -> None:
        with self.assertRaises(CallNotAuthorizedError):
            authorize_real_call(
                APPROVED_PHONE_NUMBER,
                real_calls_enabled=True,
                confirmation="yes",
            )

    def test_call_authorization_still_rejects_other_numbers(self) -> None:
        with self.assertRaises(DestinationNotAllowedError):
            authorize_real_call(
                "+1-805-439-8009",
                real_calls_enabled=True,
                confirmation=REAL_CALL_CONFIRMATION,
            )


if __name__ == "__main__":
    unittest.main()
