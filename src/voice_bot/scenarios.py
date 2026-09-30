"""Load and validate fictional patient scenarios."""

import json
from pathlib import Path
from typing import Any


DEFAULT_SCENARIOS_PATH = (
    Path(__file__).resolve().parents[2] / "scenarios" / "scenarios.json"
)

REQUIRED_FIELDS = {
    "id",
    "title",
    "category",
    "patient",
    "goal",
    "known_facts",
    "conversation_style",
    "success_criteria",
    "safety_rules",
}


class ScenarioError(ValueError):
    """Raised when scenario data is missing or invalid."""


def load_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    """Read and validate every scenario from a JSON file."""
    scenario_path = path or DEFAULT_SCENARIOS_PATH

    try:
        with scenario_path.open(encoding="utf-8") as scenario_file:
            scenarios = json.load(scenario_file)
    except FileNotFoundError as error:
        raise ScenarioError(f"Scenario file not found: {scenario_path}") from error
    except json.JSONDecodeError as error:
        raise ScenarioError(f"Scenario file is not valid JSON: {error}") from error

    if not isinstance(scenarios, list) or not scenarios:
        raise ScenarioError("The scenario file must contain a non-empty list.")

    seen_ids: set[str] = set()
    for position, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict):
            raise ScenarioError(f"Scenario {position} must be a JSON object.")

        missing_fields = REQUIRED_FIELDS - scenario.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ScenarioError(f"Scenario {position} is missing: {missing}.")

        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ScenarioError(f"Scenario {position} must have a non-empty id.")
        if scenario_id in seen_ids:
            raise ScenarioError(f"Duplicate scenario id: {scenario_id}.")
        seen_ids.add(scenario_id)

    return scenarios


def get_scenario(scenario_id: str, path: Path | None = None) -> dict[str, Any]:
    """Find one validated scenario by its unique ID."""
    for scenario in load_scenarios(path):
        if scenario["id"] == scenario_id:
            return scenario

    raise ScenarioError(f"Unknown scenario id: {scenario_id}.")
