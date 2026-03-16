from src.services.email_service import build_welcome_email_payload


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
