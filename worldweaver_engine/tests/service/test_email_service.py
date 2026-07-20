from src.services.email_service import (
    build_email_verification_payload,
    build_password_reset_email_payload,
    build_welcome_email_payload,
)
from src.config import settings


def test_build_welcome_email_payload_uses_shared_world_copy():
    payload = build_welcome_email_payload("dale@example.com", "Dale")

    assert payload["to"] == ["dale@example.com"]
    assert payload["subject"] == "Welcome to WorldWeaver"
    assert "persistent shared world" in payload["text"]
    assert "world continues when you leave" in payload["text"]
    assert "Live simply so others can simply live." in payload["text"]
    assert "<strong>Dale</strong>" in payload["html"]


def test_build_welcome_email_payload_escapes_display_name_in_html():
    payload = build_welcome_email_payload("dale@example.com", "<Dale>")

    assert "<strong>&lt;Dale&gt;</strong>" in payload["html"]
    assert "<strong><Dale></strong>" not in payload["html"]


def test_password_reset_link_prefers_human_client_url(monkeypatch):
    monkeypatch.setattr(settings, "client_url", "https://play.example")
    monkeypatch.setattr(settings, "public_url", "https://api.example")

    payload = build_password_reset_email_payload("dale@example.com", "Dale", "once-only")

    assert "https://play.example/?reset_token=once-only" in payload["text"]
    assert "https://api.example" not in payload["text"]


def test_email_verification_link_prefers_human_client_url(monkeypatch):
    monkeypatch.setattr(settings, "client_url", "https://play.example")
    monkeypatch.setattr(settings, "public_url", "https://api.example")

    payload = build_email_verification_payload("dale@example.com", "verify-once")

    assert "https://play.example/?verify_token=verify-once" in payload["text"]
    assert "https://api.example" not in payload["text"]
    assert payload["subject"] == "Confirm your WorldWeaver email"
