# Architecture

## Purpose

This project will test Pretty Good AI's healthcare voice agent by acting as a
fictional patient during authorized assessment calls. It is designed to call
only `+1-805-439-8008`.

The system is intentionally small: one Python application coordinates the
scenario, telephone audio, AI patient, recording, transcription, and report.

## High-level design

```text
Scenario JSON
     |
     v
Python application <----> OpenAI Realtime API
     |
     v
Twilio Programmable Voice <----> Approved assessment number
     |
     v
Dual-channel recording -> transcription -> bug report
```

## Components

### Scenario manager

The scenario manager loads a fictional patient from `scenarios/scenarios.json`.
Each scenario defines the patient's goal, known facts, conversation style,
success criteria, and safety rules. Scenarios contain guidance rather than a
fixed script so the conversation can respond naturally.

### Prompt builder

The prompt builder converts one validated scenario into instructions for the
AI patient. It tells the AI to use only scenario facts, avoid medical advice,
handle questions naturally, and say when information is unknown.

### Call safety

Telephone functionality must call the safety layer immediately before asking
Twilio to create a call. Authorization requires all of the following:

1. The destination normalizes to exactly `+18054398008`.
2. The `ENABLE_REAL_CALLS` environment setting is `true`.
3. The exact confirmation phrase is supplied for that run.

The destination is a code constant rather than an environment setting. This
prevents a changed configuration value from allowing another number. Tests use
fake inputs and never contact Twilio.

### Telephony

Twilio Programmable Voice is the telephone provider. The call module requests
one outbound call only after the safety checks pass. Twilio then
connect the call to the Python server through a bidirectional Media Stream.

Twilio documentation:

- https://www.twilio.com/docs/voice/api/call-resource
- https://www.twilio.com/docs/voice/media-streams

### Realtime patient voice

The Python server maintains a server-to-server WebSocket connection to the
OpenAI Realtime API. It will forward the healthcare agent's audio to the model
and send the model's fictional-patient audio back to Twilio.

The implementation uses a speech-to-speech connection because it supports
natural turn taking and interruptions without building separate live
speech-to-text and text-to-speech loops.

OpenAI documentation:

- https://developers.openai.com/api/docs/guides/voice-agents
- https://developers.openai.com/api/docs/guides/realtime-websocket

### Recording

Twilio is asked to record both call legs in dual-channel mode. Keeping the
speakers on separate channels makes later review and transcription easier. The
finished recording will be downloaded as MP3 after Twilio reports that it is
ready.

Recording must be used only for the authorized assessment and in accordance
with the challenge rules and applicable consent requirements.

Twilio documentation:

- https://www.twilio.com/docs/voice/api/recording

### Transcription

After a call ends, the recorded file can be sent to an OpenAI file
transcription model. The application will save a timestamped transcript as a
local file. Live transcription is not required for the first version because
the Realtime model handles the conversation directly.

OpenAI documentation:

- https://developers.openai.com/api/docs/guides/transcription

### Bug analysis

The analysis component will compare the completed transcript with the selected
scenario's goal and success criteria. It will produce structured findings with:

- what happened;
- why it is a problem;
- the call identifier;
- supporting transcript evidence;
- an approximate timestamp;
- severity and suggested follow-up.

The report will describe observed behavior. It must not invent events that are
not supported by the transcript.

## Call data flow

1. The user chooses one scenario.
2. Python validates the scenario and builds the fictional-patient prompt.
3. The safety layer validates the one approved destination.
4. The user explicitly enables and confirms a real call.
5. Twilio calls the assessment number and starts recording both call legs.
6. Twilio opens a secure bidirectional WebSocket to the Python server.
7. Python opens a secure WebSocket to OpenAI Realtime.
8. Python relays audio between Twilio and the fictional AI patient.
9. Turn detection manages speaking, silence, and interruption events.
10. The call ends and signed Twilio callbacks update the local run metadata.
11. Twilio's recording callback stores the completed recording ID.
12. An operator verifies the diarization speaker mapping and explicitly starts
    post-call processing.
13. Python downloads the dual-channel MP3 into the call's output folder.
14. The transcription component produces a timestamped transcript.
15. The analysis component evaluates the transcript against the scenario.
16. Python saves a human-readable bug report and marks the run review-ready.

## Planned output layout

Each run will receive a unique call ID and its own directory:

```text
output/
└── <call-id>/
    ├── metadata.json
    ├── recording.mp3
    ├── transcript.json
    ├── transcript.md
    └── bug-report.md
```

`metadata.json` will identify the scenario, timestamps, provider call ID, and
completion status. It must not contain API keys.

## Secrets and configuration

Secrets will be read from a local `.env` file or process environment. The real
`.env` file is ignored by Git. `.env.example` contains only empty placeholders.
Secrets must never appear in logs, recordings metadata, transcripts, tests, or
committed files.

## Python libraries

- `fastapi` and `uvicorn`: HTTP callbacks and Twilio WebSocket endpoint.
- `websockets`: server-to-server OpenAI Realtime connection.
- `twilio`: outbound calls, status callbacks, and recording downloads.
- `openai`: post-call transcription and transcript analysis.
- `python-dotenv`: local development environment settings.

No database, browser interface, container system, or distributed services are
planned for the first version.

## Deployment boundary

The code through offline end-to-end simulation and real provider adapters is
implemented. Deployment still requires real accounts, public TLS,
recording-consent review, explicit spending approval,
and one monitored assessment call. Speaker labels returned by diarization must
be verified before they are treated as patient and healthcare-agent labels.
