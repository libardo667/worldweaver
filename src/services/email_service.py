"""Email service — welcome emails via Resend. Fire-and-forget; swallows errors."""
from __future__ import annotations

import logging

from ..config import settings

logger = logging.getLogger(__name__)


def send_welcome_email(to_email: str, display_name: str) -> None:
    """Send a welcome email. Non-blocking — never raises."""
    if not settings.resend_api_key:
        logger.debug("RESEND_API_KEY not set — skipping welcome email to %s", to_email)
        return
    try:
        import resend  # deferred so missing package doesn't break startup

        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Welcome to WorldWeaver",
                "html": (
                    f"<p>Welcome, <strong>{display_name}</strong>!</p>"
                    "<p>Your account is active. Enter the world whenever you're ready.</p>"
                ),
            }
        )
        logger.info("Welcome email sent to %s", to_email)
    except Exception as exc:
        logger.warning("Failed to send welcome email to %s: %s", to_email, exc)
