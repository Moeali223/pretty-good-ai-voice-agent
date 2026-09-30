# Bug report

- Call ID: `CA64e23016f43aa496d6f67c5149c40244`
- Scenario ID: `no_availability_010`
- Offline findings: 1

## Findings

### 1. incorrect_patient_name

- Severity: high
- Approximate timestamp: 00:26.740
- What happened: The healthcare agent addressed the caller by the wrong name.
- Why it is a problem: Using a different patient's name during identity verification can confuse the caller and raises record-matching concerns.
- Evidence: Am I speaking with Jamie?

## Manual scenario checks

- [ ] The agent handles unavailable times without ending abruptly.
- [ ] The agent explores the stated alternative or another clear next step.
- [ ] The agent does not invent availability.
