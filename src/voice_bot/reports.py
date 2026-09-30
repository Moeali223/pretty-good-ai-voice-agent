"""Generate transparent offline quality reports from call transcripts."""

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from voice_bot.scenarios import get_scenario
from voice_bot.transcripts import Speaker, TranscriptSegment


LONG_SILENCE_MS = 8_000
SLOW_BARGE_IN_MS = 1_500


class Severity(StrEnum):
    """Simple severity labels for assessment findings."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


@dataclass(frozen=True)
class BugFinding:
    """One evidence-backed quality issue."""

    code: str
    severity: Severity
    what_happened: str
    why_problem: str
    timestamp_ms: int | None
    evidence: str


@dataclass(frozen=True)
class BugReport:
    """Offline findings and scenario checks for one call."""

    call_id: str
    scenario_id: str
    findings: list[BugFinding]
    manual_checks: list[str]


def analyze_transcript(
    call_id: str,
    scenario_id: str,
    segments: list[TranscriptSegment],
) -> BugReport:
    """Apply small deterministic checks without calling an AI service."""
    scenario = get_scenario(scenario_id)
    findings: list[BugFinding] = []
    speakers = {segment.speaker for segment in segments}

    for speaker, label in (
        (Speaker.PATIENT, "patient"),
        (Speaker.HEALTHCARE_AGENT, "healthcare agent"),
    ):
        if speaker not in speakers:
            findings.append(
                BugFinding(
                    code=f"missing_{speaker.value}",
                    severity=Severity.HIGH,
                    what_happened=f"No {label} speech appears in the transcript.",
                    why_problem="A two-sided voice assessment cannot be evaluated.",
                    timestamp_ms=None,
                    evidence="No matching transcript segments were found.",
                )
            )

    for previous, current in zip(segments, segments[1:]):
        silence_ms = current.start_ms - previous.end_ms
        if silence_ms >= LONG_SILENCE_MS:
            findings.append(
                BugFinding(
                    code="long_silence",
                    severity=Severity.WARNING,
                    what_happened=f"The conversation was silent for {silence_ms / 1000:.1f} seconds.",
                    why_problem="A long unexplained pause can make the caller think the system failed.",
                    timestamp_ms=previous.end_ms,
                    evidence=f"Gap after: {previous.text.strip()}",
                )
            )

    previous_agent_text: str | None = None
    for segment in segments:
        if segment.speaker is not Speaker.HEALTHCARE_AGENT:
            continue
        normalized_text = " ".join(segment.text.lower().split())
        if normalized_text == previous_agent_text:
            findings.append(
                BugFinding(
                    code="repeated_agent_response",
                    severity=Severity.WARNING,
                    what_happened="The healthcare agent repeated the same response.",
                    why_problem="Repetition can trap the caller in a conversational loop.",
                    timestamp_ms=segment.start_ms,
                    evidence=segment.text.strip(),
                )
            )
        previous_agent_text = normalized_text

    agent_segments = [
        segment for segment in segments if segment.speaker is Speaker.HEALTHCARE_AGENT
    ]
    patient_segments = [segment for segment in segments if segment.speaker is Speaker.PATIENT]
    for patient in patient_segments:
        for agent in agent_segments:
            continued_ms = agent.end_ms - patient.start_ms
            if agent.start_ms < patient.start_ms < agent.end_ms and continued_ms >= SLOW_BARGE_IN_MS:
                findings.append(
                    BugFinding(
                        code="slow_barge_in",
                        severity=Severity.WARNING,
                        what_happened=(
                            "The healthcare agent continued speaking for "
                            f"{continued_ms / 1000:.1f} seconds after the patient began."
                        ),
                        why_problem="Slow interruption handling makes natural conversation difficult.",
                        timestamp_ms=patient.start_ms,
                        evidence=f"Patient interruption: {patient.text.strip()}",
                    )
                )
                break

    agent_text = " ".join(segment.text.strip() for segment in agent_segments)
    normalized_agent_text = " ".join(agent_text.lower().split())

    phone_requests = [
        segment
        for segment in agent_segments
        if "phone number" in segment.text.lower()
        and any(
            term in segment.text.lower()
            for term in ("provide", "tell me", "would you", "could you", "please")
        )
    ]
    spelling_requests = [
        segment
        for segment in agent_segments
        if "spell" in segment.text.lower()
        and "name" in segment.text.lower()
    ]
    if len(phone_requests) >= 2 or len(spelling_requests) >= 2:
        repeated_request = (
            phone_requests[1] if len(phone_requests) >= 2 else spelling_requests[1]
        )
        findings.append(
            BugFinding(
                code="repeated_identity_verification",
                severity=Severity.WARNING,
                what_happened=(
                    "The healthcare agent repeated an identity-verification request "
                    "after the caller had already responded."
                ),
                why_problem=(
                    "Repeating unavailable or already supplied identity questions traps "
                    "the caller in a loop and prevents progress on the actual request."
                ),
                timestamp_ms=repeated_request.start_ms,
                evidence=repeated_request.text.strip(),
            )
        )

    if scenario.get("category") in {"insurance", "office_information"}:
        identity_request = next(
            (
                segment
                for segment in agent_segments
                if "name" in segment.text.lower()
                and "date of birth" in segment.text.lower()
            ),
            None,
        )
        if identity_request is not None:
            findings.append(
                BugFinding(
                    code="unnecessary_identity_collection",
                    severity=Severity.WARNING,
                    what_happened=(
                        "The healthcare agent requested the caller's full name and date "
                        "of birth before answering a general information question."
                    ),
                    why_problem=(
                        "Collecting identity data was unnecessary for this general question "
                        "and adds privacy and abandonment risk."
                    ),
                    timestamp_ms=identity_request.start_ms,
                    evidence=identity_request.text.strip(),
                )
            )

    language_transfer_segments = [
        segment
        for segment in agent_segments
        if "spanish" in segment.text.lower() or "español" in segment.text.lower()
    ]
    if len(language_transfer_segments) >= 2:
        findings.append(
            BugFinding(
                code="repeated_language_transfer",
                severity=Severity.HIGH,
                what_happened=(
                    "The healthcare agent repeatedly tried to transfer the caller "
                    "to a Spanish-speaking agent."
                ),
                why_problem=(
                    "Repeated transfer prompts prevented the caller's scheduling "
                    "request from progressing."
                ),
                timestamp_ms=language_transfer_segments[1].start_ms,
                evidence=language_transfer_segments[1].text.strip(),
            )
        )

    help_prompts = [
        segment
        for segment in agent_segments
        if "help you today" in " ".join(segment.text.lower().split())
    ]
    if len(help_prompts) >= 2:
        findings.append(
            BugFinding(
                code="conversation_restarted",
                severity=Severity.HIGH,
                what_happened="The healthcare agent restarted its opening question mid-call.",
                why_problem=(
                    "Restarting after collecting information loses conversational state "
                    "and forces the caller to repeat the request."
                ),
                timestamp_ms=help_prompts[-1].start_ms,
                evidence=help_prompts[-1].text.strip(),
            )
        )

    expected_name = str(scenario.get("patient", {}).get("name", ""))
    expected_first_name = expected_name.split(maxsplit=1)[0].lower() if expected_name else ""
    for segment in agent_segments:
        name_match = re.search(
            r"\bam i speaking with\s+([a-z][a-z'-]*)",
            segment.text.lower(),
        )
        if name_match and expected_first_name and name_match.group(1) != expected_first_name:
            findings.append(
                BugFinding(
                    code="incorrect_patient_name",
                    severity=Severity.HIGH,
                    what_happened="The healthcare agent addressed the caller by the wrong name.",
                    why_problem=(
                        "Using a different patient's name during identity verification can "
                        "confuse the caller and raises record-matching concerns."
                    ),
                    timestamp_ms=segment.start_ms,
                    evidence=segment.text.strip(),
                )
            )
            break

    expected_normalized_name = " ".join(expected_name.lower().split())
    for segment in agent_segments:
        confirmation_match = re.search(
            r"\bi have your name as\s+([a-z][a-z'-]*\s+[a-z][a-z'-]*)",
            segment.text.lower(),
        )
        if (
            confirmation_match
            and expected_normalized_name
            and confirmation_match.group(1) != expected_normalized_name
        ):
            findings.append(
                BugFinding(
                    code="patient_name_mistranscribed",
                    severity=Severity.HIGH,
                    what_happened=(
                        "The healthcare agent repeated the caller's name incorrectly "
                        "during identity confirmation."
                    ),
                    why_problem=(
                        "An incorrect name can cause record-matching failures and risks "
                        "associating the request with the wrong patient."
                    ),
                    timestamp_ms=segment.start_ms,
                    evidence=segment.text.strip(),
                )
            )
            break

    expected_birth_date = str(scenario.get("patient", {}).get("date_of_birth", ""))
    birth_date_segments = [
        segment
        for segment in agent_segments
        if "date of birth" in segment.text.lower()
        and re.search(r"\b(?:19|20)\d{2}\b", segment.text)
    ]
    if birth_date_segments and expected_birth_date:
        expected_year = expected_birth_date.split("-", 1)[0]
        incorrect_segment = next(
            (
                segment
                for segment in birth_date_segments
                if expected_year not in segment.text
            ),
            None,
        )
        if incorrect_segment is not None:
            findings.append(
                BugFinding(
                    code="incorrect_patient_identity",
                    severity=Severity.HIGH,
                    what_happened="The healthcare agent stated a birth date that did not match the scenario.",
                    why_problem=(
                        "Inventing or changing identity data can create the wrong patient "
                        "record and is unsafe in a healthcare workflow."
                    ),
                    timestamp_ms=incorrect_segment.start_ms,
                    evidence=incorrect_segment.text.strip(),
                )
            )

    if scenario.get("category") == "scheduling" and len(agent_segments) >= 3:
        scheduling_outcome_terms = (
            "appointment is confirmed",
            "appointment is scheduled",
            "appointment is set",
            "scheduled for",
            "available at",
            "next step",
        )
        if not any(term in normalized_agent_text for term in scheduling_outcome_terms):
            findings.append(
                BugFinding(
                    code="no_scheduling_outcome",
                    severity=Severity.HIGH,
                    what_happened="The call ended without an appointment or a clear next step.",
                    why_problem="The primary scheduling goal was not completed.",
                    timestamp_ms=segments[-1].end_ms if segments else None,
                    evidence=f"Final transcript segment: {segments[-1].text.strip()}",
                )
            )

    if scenario.get("category") == "rescheduling":
        original_status_terms = (
            "original appointment remains",
            "original appointment is still",
            "original appointment was released",
            "original appointment has been released",
            "original appointment was canceled",
            "original appointment was cancelled",
        )
        if not any(term in normalized_agent_text for term in original_status_terms):
            findings.append(
                BugFinding(
                    code="original_appointment_status_unclear",
                    severity=Severity.WARNING,
                    what_happened=(
                        "The agent ended or transferred the interaction without clarifying "
                        "whether the original appointment remained booked."
                    ),
                    why_problem=(
                        "The patient may not know whether to attend the original appointment "
                        "while waiting for rescheduling help."
                    ),
                    timestamp_ms=segments[-1].end_ms if segments else None,
                    evidence=f"Final transcript segment: {segments[-1].text.strip()}",
                )
            )

    if scenario.get("category") == "ambiguity":
        clarification_terms = (
            "what kind of appointment help",
            "what help do you need",
            "how can i help with your appointment",
            "what would you like to do with your appointment",
        )
        if not any(term in normalized_agent_text for term in clarification_terms):
            findings.append(
                BugFinding(
                    code="ambiguous_request_not_clarified",
                    severity=Severity.HIGH,
                    what_happened=(
                        "The healthcare agent began identity verification without asking "
                        "what kind of appointment help the caller needed."
                    ),
                    why_problem=(
                        "Skipping clarification adds unnecessary steps and risks routing "
                        "or handling the wrong request."
                    ),
                    timestamp_ms=agent_segments[0].start_ms if agent_segments else None,
                    evidence=(
                        agent_segments[0].text.strip()
                        if agent_segments
                        else "No healthcare-agent response was available."
                    ),
                )
            )

    return BugReport(
        call_id=call_id,
        scenario_id=scenario_id,
        findings=findings,
        manual_checks=list(scenario["success_criteria"]),
    )


def _format_timestamp(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "Not available"
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def save_bug_report(call_directory: Path, report: BugReport) -> tuple[Path, Path]:
    """Save one offline report as JSON and readable Markdown."""
    json_path = call_directory / "bug-report.json"
    json_path.write_text(
        json.dumps(asdict(report), indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Bug report",
        "",
        f"- Call ID: `{report.call_id}`",
        f"- Scenario ID: `{report.scenario_id}`",
        f"- Offline findings: {len(report.findings)}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.extend(["No issues were detected by the offline rules.", ""])
    for number, finding in enumerate(report.findings, start=1):
        lines.extend(
            [
                f"### {number}. {finding.code}",
                "",
                f"- Severity: {finding.severity}",
                f"- Approximate timestamp: {_format_timestamp(finding.timestamp_ms)}",
                f"- What happened: {finding.what_happened}",
                f"- Why it is a problem: {finding.why_problem}",
                f"- Evidence: {finding.evidence}",
                "",
            ]
        )

    lines.extend(["## Manual scenario checks", ""])
    lines.extend(f"- [ ] {check}" for check in report.manual_checks)
    lines.append("")

    markdown_path = call_directory / "bug-report.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
