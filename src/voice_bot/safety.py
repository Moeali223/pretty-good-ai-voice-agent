"""Safety checks that must pass before any live phone call."""

import re


APPROVED_PHONE_NUMBER = "+18054398008"
REAL_CALL_CONFIRMATION = "CALL APPROVED ASSESSMENT NUMBER"


class DestinationNotAllowedError(ValueError):
    """Raised when a phone number is not the approved assessment number."""


class CallNotAuthorizedError(PermissionError):
    """Raised when a real call has not passed every authorization check."""


def normalize_phone_number(phone_number: str) -> str:
    """Convert a US phone number written with common punctuation to E.164."""
    if not isinstance(phone_number, str) or not phone_number.strip():
        raise DestinationNotAllowedError("A destination phone number is required.")

    digits = re.sub(r"\D", "", phone_number)
    if len(digits) == 10:
        digits = f"1{digits}"

    if len(digits) != 11 or not digits.startswith("1"):
        raise DestinationNotAllowedError("The destination phone number is invalid.")

    return f"+{digits}"


def require_approved_destination(phone_number: str) -> str:
    """Return the normalized destination, or reject it if it is not approved."""
    normalized = normalize_phone_number(phone_number)
    if normalized != APPROVED_PHONE_NUMBER:
        raise DestinationNotAllowedError(
            "Calls are allowed only to the approved assessment number."
        )
    return normalized


def authorize_real_call(
    phone_number: str,
    *,
    real_calls_enabled: bool,
    confirmation: str,
) -> str:
    """Authorize one call only after all independent safety checks pass."""
    destination = require_approved_destination(phone_number)

    if not real_calls_enabled:
        raise CallNotAuthorizedError(
            "Real calls are disabled. ENABLE_REAL_CALLS must be true."
        )

    if confirmation != REAL_CALL_CONFIRMATION:
        raise CallNotAuthorizedError(
            "The exact real-call confirmation phrase is required."
        )

    return destination
