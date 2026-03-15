"""Helpers for encrypting actor-bound secrets with a shared federation key."""

from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings

log = logging.getLogger(__name__)


def _secret_material() -> str:
    explicit = str(settings.data_encryption_key or "").strip()
    if explicit:
        return explicit
    fallback = str(settings.jwt_secret or "").strip()
    log.warning("WW_DATA_ENCRYPTION_KEY not set; falling back to WW_JWT_SECRET for secret encryption.")
    return fallback


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    digest = hashlib.sha256(_secret_material().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_text(plaintext: str) -> str:
    raw = str(plaintext or "").strip()
    if not raw:
        return ""
    return _fernet().encrypt(raw.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str | None) -> str | None:
    raw = str(ciphertext or "").strip()
    if not raw:
        return None
    try:
        return _fernet().decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        log.warning("Failed to decrypt actor secret; ignoring cached value.")
        return None
