"""Validate that live webhook and WebSocket requests came from Twilio."""

from collections.abc import Mapping
from urllib.parse import urljoin, urlparse, urlunparse

from twilio.request_validator import RequestValidator


class TwilioRequestValidationError(ValueError):
    """Raised when a Twilio request cannot be authenticated."""


def public_request_url(
    public_base_url: str,
    path: str,
    query: str = "",
    *,
    websocket: bool = False,
) -> str:
    """Rebuild the exact public URL Twilio used, ignoring proxy-local details."""
    parsed = urlparse(public_base_url.rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise TwilioRequestValidationError(
            "PUBLIC_BASE_URL must be a complete HTTPS URL."
        )
    scheme = "wss" if websocket else "https"
    joined = urlparse(urljoin(f"{public_base_url.rstrip('/')}/", path.lstrip("/")))
    return urlunparse((scheme, joined.netloc, joined.path, "", query, ""))


def validate_twilio_signature(
    *,
    auth_token: str | None,
    signature: str | None,
    url: str,
    parameters: Mapping[str, str] | object | None = None,
    allow_trailing_slash: bool = False,
) -> None:
    """Raise unless the Twilio SDK validates the signed URL and parameters."""
    if not auth_token:
        raise TwilioRequestValidationError("TWILIO_AUTH_TOKEN is missing.")
    if not signature:
        raise TwilioRequestValidationError("X-Twilio-Signature is missing.")

    validator = RequestValidator(auth_token)
    values = parameters or {}
    valid = validator.validate(url, values, signature)
    if not valid and allow_trailing_slash and not urlparse(url).path.endswith("/"):
        parsed = urlparse(url)
        slash_url = urlunparse(
            (parsed.scheme, parsed.netloc, f"{parsed.path}/", "", parsed.query, "")
        )
        valid = validator.validate(slash_url, values, signature)
    if not valid:
        raise TwilioRequestValidationError("Twilio request signature is invalid.")
