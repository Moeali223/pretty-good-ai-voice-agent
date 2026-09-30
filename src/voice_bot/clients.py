"""Construct real service clients only after explicit live configuration."""

from typing import Any

from voice_bot.config import Configuration


def create_twilio_client(configuration: Configuration) -> Any:
    if not configuration.twilio_account_sid or not configuration.twilio_auth_token:
        raise ValueError("Twilio account credentials are required.")
    from twilio.rest import Client

    return Client(configuration.twilio_account_sid, configuration.twilio_auth_token)


def create_openai_client(configuration: Configuration) -> Any:
    if not configuration.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required.")
    from openai import OpenAI

    return OpenAI(api_key=configuration.openai_api_key)
