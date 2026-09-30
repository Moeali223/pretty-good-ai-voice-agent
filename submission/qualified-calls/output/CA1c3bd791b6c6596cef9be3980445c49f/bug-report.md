# Bug report

- Call ID: `CA1c3bd791b6c6596cef9be3980445c49f`
- Scenario ID: `cancel_appointment_003`
- Offline findings: 1

## Findings

### 1. incorrect_patient_name

- Severity: high
- Approximate timestamp: 00:23.732
- What happened: The healthcare agent addressed the caller by the wrong name.
- Why it is a problem: Using a different patient's name during identity verification can confuse the caller and raises record-matching concerns.
- Evidence: Am I speaking with Jamie?

## Manual scenario checks

- [ ] The correct appointment is identified.
- [ ] The cancellation is confirmed or a clear next step is given.
- [ ] The agent does not force the patient to reschedule.
