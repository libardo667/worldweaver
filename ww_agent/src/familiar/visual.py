# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Turn an allowed image or PDF read into text and optional image blocks.

The filesystem boundary remains in :mod:`file_scope`. This module receives only
bytes that have already passed that boundary. Digital PDFs become text for every
resident; images and scanned PDF pages are included only when the resident has an
explicit vision grant.
"""

from __future__ import annotations

import base64
import os
import struct
import zlib
from typing import Any

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}
_MAX_PDF_PAGES = 12
_MAX_RENDERED_PAGES = 5
_RENDER_SCALE = 2.0
_SCANNED_TEXT_FLOOR = 16


def kind_of(name: str, data: bytes = b"") -> str | None:
    """Classify supported visual data by extension or common magic bytes."""
    ext = os.path.splitext(str(name or ""))[1].lower()
    if ext == ".pdf" or data[:5] == b"%PDF-":
        return "pdf"
    if ext in _IMAGE_MIME:
        return "image"
    if (
        data[:8] == b"\x89PNG\r\n\x1a\n"
        or data[:3] == b"\xff\xd8\xff"
        or data[:6] in (b"GIF87a", b"GIF89a")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    ):
        return "image"
    return None


def _image_mime(name: str, data: bytes) -> str:
    ext = os.path.splitext(str(name or ""))[1].lower()
    if ext in _IMAGE_MIME:
        return _IMAGE_MIME[ext]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def image_data_url(name: str, data: bytes) -> str:
    """Return an OpenAI-compatible data URL for one image."""
    return f"data:{_image_mime(name, data)};base64," + base64.b64encode(data).decode(
        "ascii"
    )


def _png_encode(
    width: int, height: int, channels: int, raw: bytes, src_stride: int
) -> bytes:
    """Encode RGB/RGBA rows as PNG without adding Pillow or NumPy."""
    color_type = 6 if channels == 4 else 2
    row_len = width * channels
    scan = bytearray()
    for y in range(height):
        offset = y * src_stride
        scan.append(0)
        scan += raw[offset : offset + row_len]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", checksum)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        signature
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(scan), 6))
        + chunk(b"IEND", b"")
    )


def _render_page_png(page: Any) -> bytes:
    bitmap = page.render(scale=_RENDER_SCALE, rev_byteorder=True)
    return _png_encode(
        bitmap.width,
        bitmap.height,
        bitmap.n_channels,
        bytes(bitmap.buffer),
        bitmap.stride,
    )


def pdf_to_perception(
    data: bytes,
    *,
    want_images: bool,
    max_pages: int = _MAX_PDF_PAGES,
    max_rendered: int = _MAX_RENDERED_PAGES,
) -> dict[str, Any]:
    """Extract bounded PDF text and optionally render bounded scanned pages."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    total = len(document)
    parts: list[str] = []
    images: list[str] = []
    scanned = 0
    try:
        for index in range(min(total, max_pages)):
            page = document[index]
            text_page = page.get_textpage()
            text = (text_page.get_text_bounded() or "").strip()
            if len(text.replace(" ", "").replace("\n", "")) < _SCANNED_TEXT_FLOOR:
                scanned += 1
                if want_images and len(images) < max_rendered:
                    encoded = base64.b64encode(_render_page_png(page)).decode("ascii")
                    images.append("data:image/png;base64," + encoded)
            if text:
                parts.append(f"[page {index + 1}]\n{text}")
    finally:
        document.close()
    return {
        "text": "\n\n".join(parts),
        "images": images,
        "pages": total,
        "rendered": len(images),
        "scanned": scanned,
    }


def to_perception(name: str, data: bytes, *, want_images: bool) -> dict[str, Any]:
    """Describe supported visual bytes honestly for the resident's capabilities."""
    kind = kind_of(name, data)
    if kind == "image":
        if want_images:
            return {
                "kind": "image",
                "text": "",
                "images": [image_data_url(name, data)],
                "note": f"the image {name}",
            }
        return {
            "kind": "image",
            "text": "",
            "images": [],
            "note": f"{name} is an image, which this resident cannot see",
        }
    if kind == "pdf":
        perception = pdf_to_perception(data, want_images=want_images)
        details = [f"a PDF, {perception['pages']} page(s)"]
        if perception["scanned"]:
            if perception["rendered"]:
                scan_note = f"{perception['scanned']} scanned, {perception['rendered']} shown as images"
            elif not want_images:
                scan_note = (
                    f"{perception['scanned']} scanned, which this resident cannot see"
                )
            else:
                scan_note = f"{perception['scanned']} scanned"
            details.append(scan_note)
        return {
            "kind": "pdf",
            "text": perception["text"],
            "images": perception["images"],
            "note": f"{name}: " + "; ".join(details),
            "pages": perception["pages"],
            "scanned": perception["scanned"],
            "rendered": perception["rendered"],
        }
    return {
        "kind": None,
        "text": "",
        "images": [],
        "note": f"{name} is not a readable image or PDF",
    }
