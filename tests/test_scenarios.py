"""Tests for loading fictional patient scenarios."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.scenarios import ScenarioError, get_scenario, load_scenarios


class ScenarioLoaderTests(unittest.TestCase):
    def test_loads_project_scenario(self) -> None:
        scenarios = load_scenarios()

        self.assertEqual(len(scenarios), 10)
        self.assertEqual(scenarios[0]["id"], "schedule_appointment_001")

    def test_finds_scenario_by_id(self) -> None:
        scenario = get_scenario("schedule_appointment_001")

        self.assertEqual(scenario["category"], "scheduling")

    def test_rejects_unknown_id(self) -> None:
        with self.assertRaises(ScenarioError):
            get_scenario("does_not_exist")

    def test_rejects_scenario_with_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "invalid.json"
            path.write_text(json.dumps([{"id": "incomplete"}]), encoding="utf-8")

            with self.assertRaises(ScenarioError):
                load_scenarios(path)

    def test_rejects_duplicate_ids(self) -> None:
        scenario = load_scenarios()[0]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "duplicates.json"
            path.write_text(json.dumps([scenario, scenario]), encoding="utf-8")

            with self.assertRaises(ScenarioError):
                load_scenarios(path)


if __name__ == "__main__":
    unittest.main()
