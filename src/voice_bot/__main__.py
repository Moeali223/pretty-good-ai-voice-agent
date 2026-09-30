"""Offline command-line tools for inspecting patient scenarios."""

import argparse
import json
from collections.abc import Sequence

from voice_bot.prompts import build_patient_prompt
from voice_bot.clients import create_openai_client, create_twilio_client
from voice_bot.config import load_configuration
from voice_bot.safety import REAL_CALL_CONFIRMATION
from voice_bot.post_call import process_completed_call
from voice_bot.recordings import TwilioRecordingProvider
from voice_bot.runs import (
    CallStatus,
    RunRecordError,
    create_call_run,
    get_call_directory,
    update_call_status,
)
from voice_bot.scenarios import get_scenario, load_scenarios
from voice_bot.simulation import simulate_call_lifecycle
from voice_bot.telephony import TwilioCallProvider, create_assessment_call
from voice_bot.transcription import OpenAITranscriptionProvider
from voice_bot.transcripts import Speaker


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="voice_bot",
        description="Simulate or safely run fictional-patient assessments.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="List every available scenario.")

    preview_parser = commands.add_parser(
        "preview",
        help="Print the patient prompt for one scenario.",
    )
    preview_parser.add_argument("scenario_id", help="ID of the scenario to preview.")

    simulate_parser = commands.add_parser(
        "simulate",
        help="Create an offline call lifecycle record for one scenario.",
    )
    simulate_parser.add_argument("scenario_id", help="ID of the scenario to simulate.")

    call_parser = commands.add_parser(
        "call",
        help="Place one safety-guarded assessment call (uses paid services).",
    )
    call_parser.add_argument("scenario_id", help="ID of the scenario to run.")
    call_parser.add_argument(
        "--confirm",
        required=True,
        help=f"Must exactly equal: {REAL_CALL_CONFIRMATION}",
    )

    process_parser = commands.add_parser(
        "process-call",
        help="Download, transcribe, and report on one completed call.",
    )
    process_parser.add_argument("call_id", help="Twilio CallSid to process.")
    process_parser.add_argument(
        "--patient-label",
        required=True,
        help="Verified diarization label for the fictional patient.",
    )
    process_parser.add_argument(
        "--agent-label",
        required=True,
        help="Verified diarization label for the healthcare agent.",
    )
    process_parser.add_argument(
        "--system-label",
        action="append",
        default=[],
        help="Diarization label for an automated announcement; may be repeated.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one offline scenario-inspection command."""
    args = build_parser().parse_args(argv)

    if args.command == "list":
        for scenario in load_scenarios():
            print(f"{scenario['id']}: {scenario['title']}")
        return 0

    if args.command == "preview":
        scenario = get_scenario(args.scenario_id)
        print(build_patient_prompt(scenario))
        return 0

    if args.command == "simulate":
        call_directory = simulate_call_lifecycle(args.scenario_id)
        print("Offline simulation completed.")
        print(f"Output: {call_directory}")
        return 0

    if args.command == "process-call":
        patient_label = args.patient_label.strip()
        agent_label = args.agent_label.strip()
        system_labels = [label.strip() for label in args.system_label]
        labels = [patient_label, agent_label, *system_labels]
        if any(not label for label in labels) or len(set(labels)) != len(labels):
            raise RunRecordError(
                "Patient, healthcare-agent, and system labels must be non-empty "
                "and different."
            )

        configuration = load_configuration()
        if not configuration.twilio_account_sid:
            raise ValueError("TWILIO_ACCOUNT_SID is required.")
        call_directory = get_call_directory(args.call_id)
        metadata = json.loads(
            (call_directory / "metadata.json").read_text(encoding="utf-8")
        )
        recording_id = metadata.get("recording_id")
        if not isinstance(recording_id, str) or not recording_id:
            raise RunRecordError("The call has no completed recording ID.")

        openai_client = create_openai_client(configuration)
        process_completed_call(
            call_directory,
            recording_provider=TwilioRecordingProvider(
                configuration.twilio_account_sid,
                configuration.twilio_auth_token or "",
            ),
            recording_id=recording_id,
            transcription_provider=OpenAITranscriptionProvider(
                openai_client,
                speaker_map={
                    patient_label: Speaker.PATIENT,
                    agent_label: Speaker.HEALTHCARE_AGENT,
                    **{label: Speaker.SYSTEM for label in system_labels},
                },
            ),
        )
        print("Completed call artifacts are ready for review.")
        print(f"Output: {call_directory}")
        return 0

    configuration = load_configuration(require_services=True)
    client = create_twilio_client(configuration)
    prepared = create_assessment_call(
        TwilioCallProvider(client),
        configuration,
        scenario_id=args.scenario_id,
        confirmation=args.confirm,
    )
    call_directory = create_call_run(
        args.scenario_id,
        call_id=prepared.provider_call_id,
    )
    update_call_status(call_directory, CallStatus.QUEUED)
    print(f"Authorized assessment call created: {prepared.provider_call_id}")
    print(f"Output: {call_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
