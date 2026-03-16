"""Email service — welcome emails via Resend. Fire-and-forget; swallows errors."""
from __future__ import annotations

from html import escape
import logging

from ..config import settings

logger = logging.getLogger(__name__)


def build_welcome_email_payload(to_email: str, display_name: str) -> dict[str, object]:
    safe_name = escape(display_name.strip() or "traveler")
    raw_name = display_name.strip() or "traveler"
    text_body = "\n".join(
        [
            f"Welcome, {raw_name}.",
            "",
            "WorldWeaver is a persistent shared world.",
            "Human visitors and AI residents live here at the same time.",
            "You are not starting the story. You are arriving inside it, and the world continues when you leave.",
            "",
            "Your account is active. Enter when you're ready, move gently, and take your time.",
            "",
            "Live simply so others can simply live.",
        ]
    )
    html_body = "".join(
        [
            f"<p>Welcome, <strong>{safe_name}</strong>.</p>",
            "<p>WorldWeaver is a persistent shared world.</p>",
            "<p>Human visitors and AI residents live here at the same time.</p>",
            "<p>You are not starting the story. You are arriving inside it, and the world continues when you leave.</p>",
            "<p>Your account is active. Enter when you're ready, move gently, and take your time.</p>",
            "<p><em>Live simply so others can simply live.</em></p>",
        ]
    )
    return {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Welcome to WorldWeaver",
        "text": text_body,
        "html": html_body,
    }


def send_welcome_email(to_email: str, display_name: str) -> None:
    """Send a welcome email. Non-blocking — never raises."""
    if not settings.resend_api_key:
        logger.debug("RESEND_API_KEY not set — skipping welcome email to %s", to_email)
        return
    try:
        import resend  # deferred so missing package doesn't break startup

        resend.api_key = settings.resend_api_key
        resend.Emails.send(build_welcome_email_payload(to_email, display_name))
        logger.info("Welcome email sent to %s", to_email)
    except Exception as exc:
        logger.warning("Failed to send welcome email to %s: %s", to_email, exc)
