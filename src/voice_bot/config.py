"""Load service settings from environment variables without exposing secrets."""

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Configuration:
    """Settings used by the Twilio and OpenAI integrations."""

    twilio_account_sid: str | None
    twilio_auth_token: str | None
    twilio_phone_number: str | None
    openai_api_key: str | None
    public_base_url: str | None
    enable_real_calls: bool


def _optional_environment_value(name: str) -> str | None:
    """Return a trimmed environment value, treating blanks as missing."""
    value = os.getenv(name, "").strip()
    return value or None


def _read_boolean(name: str, default: bool = False) -> bool:
    """Read a strict true-or-false environment setting."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ConfigurationError(f"{name} must be either true or false.")


def load_configuration(require_services: bool = False) -> Configuration:
    """Load settings, optionally requiring every live service credential."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    configuration = Configuration(
        twilio_account_sid=_optional_environment_value("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_optional_environment_value("TWILIO_AUTH_TOKEN"),
        twilio_phone_number=_optional_environment_value("TWILIO_PHONE_NUMBER"),
        openai_api_key=_optional_environment_value("OPENAI_API_KEY"),
        public_base_url=_optional_environment_value("PUBLIC_BASE_URL"),
        enable_real_calls=_read_boolean("ENABLE_REAL_CALLS"),
    )

    if require_services:
        required_values = {
            "TWILIO_ACCOUNT_SID": configuration.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": configuration.twilio_auth_token,
            "TWILIO_PHONE_NUMBER": configuration.twilio_phone_number,
            "OPENAI_API_KEY": configuration.openai_api_key,
            "PUBLIC_BASE_URL": configuration.public_base_url,
        }
        missing = [name for name, value in required_values.items() if value is None]
        if missing:
            raise ConfigurationError(
                "Missing required environment settings: " + ", ".join(missing)
            )

    return configuration
