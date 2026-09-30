"""Tests for deterministic offline transcript analysis."""

import json
import tempfile
import unittest
from pathlib import Path

from voice_bot.reports import analyze_transcript, save_bug_report
from voice_bot.transcripts import Speaker, TranscriptSegment


class BugReportTests(unittest.TestCase):
    def test_reports_long_silence_repetition_and_slow_barge_in(self) -> None:
        segments = [
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 0, 2000, "How may I help you?"
            ),
            TranscriptSegment(Speaker.PATIENT, 10_000, 11_000, "I need an appointment."),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 12_000, 16_000, "Monday morning is available."
            ),
            TranscriptSegment(
                Speaker.PATIENT, 13_000, 14_000, "Sorry, mornings do not work."
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 16_500, 18_000, "Monday morning is available."
            ),
        ]

        report = analyze_transcript(
            "fake-call-001", "schedule_appointment_001", segments
        )
        codes = {finding.code for finding in report.findings}

        self.assertIn("long_silence", codes)
        self.assertIn("repeated_agent_response", codes)
        self.assertIn("slow_barge_in", codes)

    def test_reports_missing_speaker(self) -> None:
        report = analyze_transcript(
            "fake-call-002",
            "office_hours_005",
            [TranscriptSegment(Speaker.PATIENT, 0, 1000, "What are your hours?")],
        )

        self.assertEqual(report.findings[0].code, "missing_healthcare_agent")

    def test_clean_dialogue_has_no_offline_findings(self) -> None:
        report = analyze_transcript(
            "fake-call-003",
            "office_hours_005",
            [
                TranscriptSegment(Speaker.PATIENT, 0, 1000, "What are your hours?"),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT, 1300, 3000, "We are open weekdays."
                ),
            ],
        )

        self.assertEqual(report.findings, [])
        self.assertGreater(len(report.manual_checks), 0)

    def test_reports_scheduling_loop_bad_identity_and_missing_outcome(self) -> None:
        segments = [
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 0, 1000, "How can I help you today?"
            ),
            TranscriptSegment(
                Speaker.PATIENT, 1200, 2500, "I need a Tuesday appointment."
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT,
                2700,
                4000,
                "Would you like a Spanish-speaking agent?",
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT,
                4300,
                5600,
                "I can connect you with an agent who speaks español.",
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT,
                5800,
                7500,
                "Your date of birth is July 4th, 2000.",
            ),
            TranscriptSegment(
                Speaker.HEALTHCARE_AGENT, 7800, 9000, "How may I help you today?"
            ),
        ]

        report = analyze_transcript(
            "fake-call-005", "schedule_appointment_001", segments
        )
        codes = {finding.code for finding in report.findings}

        self.assertIn("repeated_language_transfer", codes)
        self.assertIn("conversation_restarted", codes)
        self.assertIn("incorrect_patient_identity", codes)
        self.assertIn("no_scheduling_outcome", codes)

    def test_appointment_is_set_counts_as_scheduling_outcome(self) -> None:
        report = analyze_transcript(
            "fake-call-scheduled",
            "schedule_appointment_001",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I need a routine appointment."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2400,
                    "Tuesday afternoon is available.",
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    2600,
                    4000,
                    "Your appointment is set for Tuesday at 2:30 p.m.",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertNotIn("no_scheduling_outcome", codes)

    def test_birth_date_question_is_not_reported_as_incorrect_identity(self) -> None:
        report = analyze_transcript(
            "fake-call-006",
            "reschedule_appointment_002",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I need to reschedule."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2500,
                    "May I have your full name and date of birth?",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertNotIn("incorrect_patient_identity", codes)

    def test_reschedule_reports_unclear_original_appointment_status(self) -> None:
        report = analyze_transcript(
            "fake-call-007",
            "reschedule_appointment_002",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I need to move my appointment."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2500,
                    "I will transfer you to patient support.",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("original_appointment_status_unclear", codes)

    def test_reports_incorrect_patient_name(self) -> None:
        report = analyze_transcript(
            "fake-call-008",
            "cancel_appointment_003",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I need to cancel my appointment."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2400,
                    "Am I speaking with Jamie?",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("incorrect_patient_name", codes)

    def test_reports_unnecessary_identity_collection_for_general_question(self) -> None:
        report = analyze_transcript(
            "fake-call-009",
            "insurance_question_006",
            [
                TranscriptSegment(
                    Speaker.PATIENT,
                    0,
                    1000,
                    "Do you accept Blue Shield of California?",
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2600,
                    "May I have your full name and date of birth?",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("unnecessary_identity_collection", codes)

    def test_reports_ambiguous_request_not_clarified(self) -> None:
        report = analyze_transcript(
            "fake-call-010",
            "ambiguous_request_007",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I need help with my appointment."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2500,
                    "May I have your date of birth?",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("ambiguous_request_not_clarified", codes)

    def test_reports_repeated_identity_verification(self) -> None:
        report = analyze_transcript(
            "fake-call-011",
            "barge_in_008",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "I don't have that phone number."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2400,
                    "Please provide the phone number on file.",
                ),
                TranscriptSegment(
                    Speaker.PATIENT, 2600, 3500, "It is unavailable."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    3700,
                    4900,
                    "Could you provide that phone number?",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("repeated_identity_verification", codes)

    def test_reports_patient_name_mistranscription(self) -> None:
        report = analyze_transcript(
            "fake-call-012",
            "correct_information_009",
            [
                TranscriptSegment(
                    Speaker.PATIENT, 0, 1000, "My name is Drew Martinez."
                ),
                TranscriptSegment(
                    Speaker.HEALTHCARE_AGENT,
                    1200,
                    2700,
                    "I have your name as Drew Bartinez and your birth date.",
                ),
            ],
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("patient_name_mistranscribed", codes)

    def test_saves_json_and_markdown_report(self) -> None:
        report = analyze_transcript(
            "fake-call-004",
            "office_hours_005",
            [TranscriptSegment(Speaker.PATIENT, 0, 1000, "What are your hours?")],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            json_path, markdown_path = save_bug_report(
                Path(temporary_directory), report
            )
            saved_json = json.loads(json_path.read_text(encoding="utf-8"))
            saved_markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(saved_json["call_id"], "fake-call-004")
        self.assertIn("What happened", saved_markdown)
        self.assertIn("Why it is a problem", saved_markdown)
        self.assertIn("Manual scenario checks", saved_markdown)


if __name__ == "__main__":
    unittest.main()
