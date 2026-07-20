from __future__ import annotations

from src.familiar import visual

_SCANNED_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 60 40]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000052 00000 n \n0000000101 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF\n"
)


def test_visual_kind_uses_extensions_and_magic_bytes():
    png = visual._png_encode(1, 1, 3, b"\xff\x00\x00", 3)

    assert visual.kind_of("picture.png") == "image"
    assert visual.kind_of("scan.PDF") == "pdf"
    assert visual.kind_of("no-extension", png) == "image"
    assert visual.kind_of("notes.md", b"plain text") is None


def test_scanned_pdf_becomes_images_only_for_explicit_vision():
    sighted = visual.to_perception("scan.pdf", _SCANNED_PDF, want_images=True)
    text_only = visual.to_perception("scan.pdf", _SCANNED_PDF, want_images=False)

    assert sighted["scanned"] == 1
    assert sighted["images"][0].startswith("data:image/png;base64,")
    assert text_only["images"] == []
    assert "cannot see" in text_only["note"]
