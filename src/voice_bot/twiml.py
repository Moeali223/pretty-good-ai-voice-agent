"""Build TwiML instructions without contacting Twilio."""

from urllib.parse import urlparse, urlunparse
from xml.etree.ElementTree import Element, SubElement, tostring

from voice_bot.scenarios import get_scenario


class TwimlConfigurationError(ValueError):
    """Raised when safe stream instructions cannot be created."""


def _websocket_url(public_base_url: str) -> str:
    """Convert a complete public HTTPS base URL to a secure WebSocket URL."""
    parsed = urlparse(public_base_url.rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise TwimlConfigurationError(
            "The public base URL must be a complete HTTPS URL."
        )

    return urlunparse(("wss", parsed.netloc, "/twilio/media", "", "", ""))


def build_stream_twiml(scenario_id: str, public_base_url: str) -> str:
    """Return TwiML that connects one call to the live media endpoint."""
    get_scenario(scenario_id)
    stream_url = _websocket_url(public_base_url)

    response = Element("Response")
    connect = SubElement(response, "Connect")
    stream = SubElement(connect, "Stream", {"url": stream_url})
    SubElement(
        stream,
        "Parameter",
        {
            "name": "scenario_id",
            "value": scenario_id,
        },
    )

    return tostring(response, encoding="unicode", short_empty_elements=True)
