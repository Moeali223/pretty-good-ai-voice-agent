"""Tests for fictional patient prompt generation."""

import unittest

from voice_bot.prompts import build_patient_prompt
from voice_bot.scenarios import get_scenario


class PatientPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = get_scenario("schedule_appointment_001")
        self.prompt = build_patient_prompt(self.scenario)

    def test_includes_patient_and_goal(self) -> None:
        self.assertIn("Jamie Carter", self.prompt)
        self.assertIn(self.scenario["goal"], self.prompt)

    def test_includes_scenario_facts(self) -> None:
        for fact in self.scenario["known_facts"]:
            self.assertIn(fact, self.prompt)

    def test_includes_universal_safety_rules(self) -> None:
        self.assertIn("fictional patient", self.prompt)
        self.assertIn("Use only facts provided", self.prompt)
        self.assertIn("Do not provide medical advice", self.prompt)

    def test_preserves_patient_role_and_english_during_phone_menus(self) -> None:
        self.assertIn("Remain the patient for the entire call", self.prompt)
        self.assertIn("Speak only in English", self.prompt)
        self.assertIn("phone-menu prompts", self.prompt)
        self.assertIn("Never ask the office agent how you can help them", self.prompt)

    def test_steers_toward_the_scenario_goal(self) -> None:
        self.assertIn("Actively steer the conversation", self.prompt)
        self.assertIn("office gives a clear next step", self.prompt)

    def test_forbids_inventing_contact_and_identity_details(self) -> None:
        self.assertIn("Never invent a phone number", self.prompt)
        self.assertIn("identity or contact detail not listed", self.prompt)

    def test_requires_follow_up_questions_in_separate_turns(self) -> None:
        self.assertIn("Do not bundle all planned questions", self.prompt)
        self.assertIn("follow-up questions one at a time", self.prompt)

    def test_includes_scenario_specific_rules(self) -> None:
        for rule in self.scenario["safety_rules"]:
            self.assertIn(rule, self.prompt)


if __name__ == "__main__":
    unittest.main()
