"""HTML sanitization helpers — strip tags and scripts from user input."""

from __future__ import annotations

import bleach


def sanitize_text(value: str | None, *, max_length: int | None = None) -> str | None:
    """Strip all HTML tags from user-provided text and collapse whitespace."""

    if value is None:
        return None
    cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)
    cleaned = " ".join(cleaned.split())
    if max_length is not None:
        cleaned = cleaned[:max_length]
    return cleaned or None


def sanitize_required(value: str, *, max_length: int | None = None) -> str:
    """Same as sanitize_text but rejects empty/None results."""

    cleaned = sanitize_text(value, max_length=max_length)
    if not cleaned:
        raise ValueError("value is empty after sanitization")
    return cleaned
