"""Tests for offline TwiML generation."""

import unittest
from xml.etree.ElementTree import fromstring

from voice_bot.scenarios import ScenarioError
from voice_bot.twiml import TwimlConfigurationError, build_stream_twiml


class TwimlTests(unittest.TestCase):
    def test_builds_secure_stream_instructions(self) -> None:
        twiml = build_stream_twiml(
            "schedule_appointment_001",
            "https://assessment.example.test",
        )
        root = fromstring(twiml)
        stream = root.find("./Connect/Stream")
        parameter = root.find("./Connect/Stream/Parameter")

        self.assertEqual(root.tag, "Response")
        self.assertIsNotNone(stream)
        self.assertEqual(
            stream.attrib["url"],
            "wss://assessment.example.test/twilio/media",
        )
        self.assertEqual(parameter.attrib["name"], "scenario_id")
        self.assertEqual(parameter.attrib["value"], "schedule_appointment_001")

    def test_rejects_insecure_public_url(self) -> None:
        with self.assertRaises(TwimlConfigurationError):
            build_stream_twiml(
                "schedule_appointment_001",
                "http://assessment.example.test",
            )

    def test_rejects_unknown_scenario(self) -> None:
        with self.assertRaises(ScenarioError):
            build_stream_twiml(
                "does_not_exist",
                "https://assessment.example.test",
            )


if __name__ == "__main__":
    unittest.main()
