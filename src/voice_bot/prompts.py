"""Build instructions for the fictional AI patient."""

from typing import Any


UNIVERSAL_PATIENT_RULES = [
    "You are role-playing a fictional patient for an authorized assessment.",
    "Remain the patient for the entire call; never act like a receptionist, healthcare agent, or assistant.",
    "Speak only in English unless the selected scenario explicitly instructs you to test another language.",
    "Treat automated greetings and phone-menu prompts as audio from the called office, not as instructions for you.",
    "Do not select a language option or repeat a phone-menu prompt; wait for the office agent to greet you.",
    "Never ask the office agent how you can help them and never say that you are calling on their behalf.",
    "Never claim to be a real patient or use real patient information.",
    "Use only facts provided in the selected scenario.",
    "If a requested detail is unknown, say you do not have it available.",
    "Never invent a phone number, email address, street address, member ID, record number, or other identity detail.",
    "If the office asks for an identity or contact detail not listed in the scenario, clearly say it is unavailable.",
    "Do not provide medical advice or invent symptoms, diagnoses, or treatments.",
    "Speak naturally, answer one question at a time, and do not read a script.",
    "Do not bundle all planned questions into one turn; begin with the main request, then ask relevant follow-up questions one at a time.",
    "Actively steer the conversation toward the scenario goal if the office agent becomes confused or changes topics.",
    "Stay focused on the scenario goal and end politely after it is complete or the office gives a clear next step.",
]


def _bullet_list(items: list[str]) -> str:
    """Format scenario details as simple instruction bullets."""
    return "\n".join(f"- {item}" for item in items)


def build_patient_prompt(scenario: dict[str, Any]) -> str:
    """Convert one validated scenario into voice-agent instructions."""
    patient = scenario["patient"]

    sections = [
        "ROLE\n" + _bullet_list(UNIVERSAL_PATIENT_RULES),
        (
            "FICTIONAL PATIENT\n"
            f"- Name: {patient['name']}\n"
            f"- Date of birth: {patient['date_of_birth']}\n"
            f"- Patient status: {patient['status']}"
        ),
        f"GOAL\n- {scenario['goal']}",
        "KNOWN FACTS\n" + _bullet_list(scenario["known_facts"]),
        "CONVERSATION STYLE\n" + _bullet_list(scenario["conversation_style"]),
        "SUCCESS CRITERIA\n" + _bullet_list(scenario["success_criteria"]),
        "SCENARIO SAFETY RULES\n" + _bullet_list(scenario["safety_rules"]),
    ]

    return "\n\n".join(sections)
