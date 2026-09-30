"""Prepare an authorized outbound call through an injected provider."""

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from voice_bot.config import Configuration
from voice_bot.safety import (
    APPROVED_PHONE_NUMBER,
    authorize_real_call,
)
from voice_bot.scenarios import get_scenario


class TelephonyConfigurationError(ValueError):
    """Raised when telephone configuration is missing or unsafe."""


class CallProvider(Protocol):
    """Provider interface implemented by offline fakes and Twilio."""

    def create_call(self, **parameters: Any) -> str:
        """Create a call and return the provider's call ID."""


class TwilioCallProvider:
    """Small adapter around an authenticated Twilio REST client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create_call(self, **parameters: Any) -> str:
        call = self._client.calls.create(**parameters)
        call_sid = getattr(call, "sid", None)
        if not isinstance(call_sid, str) or not call_sid:
            raise TelephonyConfigurationError("Twilio did not return a call SID.")
        return call_sid


@dataclass(frozen=True)
class PreparedCall:
    """Safe summary of an accepted provider request."""

    provider_call_id: str
    scenario_id: str
    destination: str
    recording_channels: str


def _require_telephony_settings(configuration: Configuration) -> tuple[str, str]:
    """Return the source number and public URL after local validation."""
    if not configuration.twilio_phone_number:
        raise TelephonyConfigurationError("TWILIO_PHONE_NUMBER is required.")
    if not configuration.public_base_url:
        raise TelephonyConfigurationError("PUBLIC_BASE_URL is required.")

    parsed_url = urlparse(configuration.public_base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise TelephonyConfigurationError(
            "PUBLIC_BASE_URL must be a complete HTTPS URL."
        )

    return configuration.twilio_phone_number, configuration.public_base_url.rstrip("/")


def create_assessment_call(
    provider: CallProvider,
    configuration: Configuration,
    *,
    scenario_id: str,
    confirmation: str,
) -> PreparedCall:
    """Authorize and submit one assessment call to an injected provider."""
    get_scenario(scenario_id)
    source_number, base_url = _require_telephony_settings(configuration)
    destination = authorize_real_call(
        APPROVED_PHONE_NUMBER,
        real_calls_enabled=configuration.enable_real_calls,
        confirmation=confirmation,
    )

    provider_call_id = provider.create_call(
        to=destination,
        from_=source_number,
        url=urljoin(f"{base_url}/", f"twilio/answer?scenario_id={scenario_id}"),
        status_callback=urljoin(f"{base_url}/", "twilio/call-status"),
        status_callback_event=["queued", "ringing", "answered", "completed"],
        record=True,
        recording_channels="dual",
        recording_track="both",
        recording_status_callback=urljoin(
            f"{base_url}/", "twilio/recording-status"
        ),
        recording_status_callback_event=["completed"],
    )

    return PreparedCall(
        provider_call_id=provider_call_id,
        scenario_id=scenario_id,
        destination=destination,
        recording_channels="dual",
    )
