# Agent instructions

## Project

This project is an AI voice agent.

## Working guidelines

- Keep changes small and focused.
- Explain important changes in plain language.
- Follow the existing code style and structure.
- Do not modify generated or system files.
- Test relevant behavior before finishing.
- Ask before making destructive changes.

## Commands

```bash
# Install or update the editable project environment
.venv/bin/python -m pip install -e .

# Start the local development server
.venv/bin/uvicorn voice_bot.server:app --reload

# Run all tests
.venv/bin/python -m unittest discover -s tests -v

# Run an offline simulation
.venv/bin/python -m voice_bot simulate schedule_appointment_001
```

> Note: This file is at the project root, so these instructions apply to the
> entire repository.
