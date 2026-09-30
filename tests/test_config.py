"""Tests for safe environment configuration loading."""

import unittest
from unittest.mock import patch

from voice_bot.config import ConfigurationError, load_configuration


SETTING_NAMES = [
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "OPENAI_API_KEY",
    "PUBLIC_BASE_URL",
    "ENABLE_REAL_CALLS",
]


class ConfigurationTests(unittest.TestCase):
    @patch("dotenv.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_real_calls_default_to_disabled(self, load_dotenv) -> None:
        configuration = load_configuration()

        self.assertFalse(configuration.enable_real_calls)

    @patch("dotenv.load_dotenv")
    @patch.dict("os.environ", {"ENABLE_REAL_CALLS": "true"}, clear=True)
    def test_real_calls_can_be_explicitly_enabled(self, load_dotenv) -> None:
        configuration = load_configuration()

        self.assertTrue(configuration.enable_real_calls)

    @patch("dotenv.load_dotenv")
    @patch.dict("os.environ", {"ENABLE_REAL_CALLS": "maybe"}, clear=True)
    def test_rejects_invalid_boolean(self, load_dotenv) -> None:
        with self.assertRaises(ConfigurationError):
            load_configuration()

    @patch("dotenv.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_service_settings_are_reported(self, load_dotenv) -> None:
        with self.assertRaises(ConfigurationError) as context:
            load_configuration(require_services=True)

        for name in SETTING_NAMES[:-1]:
            self.assertIn(name, str(context.exception))


if __name__ == "__main__":
    unittest.main()
