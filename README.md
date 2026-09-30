# Pretty Good AI Voice-Agent Assessment Bot

This Python project was built for the Pretty Good AI Engineering Challenge. It
acts as a fictional patient and evaluates a healthcare voice agent through
natural telephone conversations.

## Current status

The project has a complete offline simulation and guarded service adapters. It can:

- validate the single approved assessment number;
- block real calls unless multiple authorization checks pass;
- load and validate 10 fictional patient scenarios;
- generate natural patient instructions from a scenario;
- list scenarios and preview their generated instructions;
- relay 8 kHz G.711 phone audio through an OpenAI Realtime adapter;
- prepare a recorded Twilio call through a Twilio adapter;
- save recordings, diarized transcripts, and deterministic bug reports;
- authenticate and persist Twilio call and recording callbacks;
- retry post-call processing without downloading a recording twice;
- test the full design with fake providers.

The live workflow has been exercised against the approved assessment number.
Ten selected call recordings, transcripts, and reports are included under
`submission/qualified-calls/`. Real calling remains disabled by default.

## Safety restrictions

The project may call only:

```text
+1-805-439-8008
```

The approved destination is hardcoded in the safety module. A real call
must pass all three checks:

1. The destination must be the approved number.
2. `ENABLE_REAL_CALLS` must explicitly be set to `true`.
3. The exact confirmation phrase must be supplied for that run.

Do not add another destination or make a real call without explicit approval.

## Requirements

- macOS, Linux, or Windows
- Python 3.12 or newer
- A terminal

The offline simulation does not need credentials or paid API usage.

## Setup

Open a terminal in this project folder:

```bash
cd /Applications/pretty-good-ai-voice-agent
```

Create the private Python environment if `.venv` does not already exist:

```bash
python3.12 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

After activation, the terminal prompt normally begins with `(.venv)`.

Install the project and its dependencies:

```bash
python -m pip install -e .
```

## Offline commands

List all 10 patient scenarios:

```bash
PYTHONPATH=src python -m voice_bot list
```

Preview the generated instructions for one scenario:

```bash
PYTHONPATH=src python -m voice_bot preview schedule_appointment_001
```

Create a local record of a fake call moving through its lifecycle:

```bash
PYTHONPATH=src python -m voice_bot simulate schedule_appointment_001
```

The simulation does not use a telephone or AI service. It writes metadata, a
fictional MP3 placeholder, a timestamped transcript, and a bug report under
`output/`.

Other scenario IDs can be found with the `list` command.

## Run the tests

The tests are offline and cannot make calls:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Configuration

[`.env.example`](.env.example) lists the settings that live service
integrations will need. It contains no real credentials.

When service integration is approved, copy the example to `.env` and add the
credentials locally:

```bash
cp .env.example .env
```

Never commit or share `.env`. The project's `.gitignore` excludes it.

## Running the server

For local development:

```bash
uvicorn voice_bot.server:app --reload
```

`GET /health` should return `{"status":"ok"}`. Twilio needs a public HTTPS URL
that forwards to this server; local-only `localhost` is not sufficient.

## Real-call safety procedure

Do not run this until the challenge owner has approved the call, recording,
API spending, and any legally required recording consent notice.

The only live command is:

```bash
python -m voice_bot call schedule_appointment_001 \
  --confirm "CALL APPROVED ASSESSMENT NUMBER"
```

It still fails unless `ENABLE_REAL_CALLS=true`, every credential is present,
and the destination passes the hardcoded allowlist. The command accepts no
destination argument, so it cannot be pointed at another number.

The first real call should be monitored. Verify recording consent, public TLS
configuration, and diarized speaker mapping
before running the remaining scenarios.

## Processing a completed call

Twilio's signed recording callback stores the completed recording ID but does
not automatically spend money on transcription. After listening to the first
recording and verifying which diarization label belongs to each participant,
run:

```bash
python -m voice_bot process-call CA_CALL_SID \
  --patient-label A \
  --agent-label B
```

Use the actual labels observed during the monitored verification; label names
are provider output and are not assumed by the application. The command downloads the MP3, requests diarized
transcription, creates transcript and bug-report files, and marks the run
`review_ready`. If transcription fails, rerun the same command; an already
downloaded MP3 is reused.

## Patient scenarios

The fictional scenarios are stored in
[`scenarios/scenarios.json`](scenarios/scenarios.json). They cover:

1. Scheduling an appointment
2. Rescheduling an appointment
3. Canceling an appointment
4. Requesting a medication refill
5. Asking about office hours
6. Asking about insurance
7. Clarifying an ambiguous request
8. Interrupting to test barge-in
9. Correcting previously supplied information
10. Handling unavailable appointment times

These are assessment personas, not real patients. Do not add real protected
health information.

## Project structure

```text
.
├── docs/
│   └── architecture.md
├── scenarios/
│   └── scenarios.json
├── src/
│   └── voice_bot/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── prompts.py
│       ├── safety.py
│       └── scenarios.py
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_prompts.py
│   ├── test_safety.py
│   └── test_scenarios.py
├── .env.example
├── .gitignore
├── AGENTS.md
├── pyproject.toml
└── README.md
```

## Architecture

The implemented path is:

```text
Scenario -> Python server -> OpenAI Realtime
                       |
                       v
                    Twilio -> approved assessment number
                       |
                       v
          recording -> transcript -> bug report
```

See [`docs/architecture.md`](docs/architecture.md) for the detailed design and
the reasons behind each technical choice.

## Assessment artifacts

The ten calls selected for review are listed in
[`submission/QUALIFYING_CALLS.md`](submission/QUALIFYING_CALLS.md). The
corresponding MP3 recordings, timestamped transcripts, metadata, and bug
reports are browsable under `submission/qualified-calls/` and are also
available as `submission/qualified-calls.zip` for convenient download.

The local `.env`, raw working output, virtual environment, tunnel binary, and
other machine-specific files are excluded from version control.
