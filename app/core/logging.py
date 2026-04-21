"""Logging setup for the loyalty agent."""

import logging
import sys

from app.core.config import settings


def preview_for_log(text: str | None, max_chars: int = 100) -> str:
    """Single-line, length-limited snippet for logs (avoid dumping full user/LLM text)."""
    if not text:
        return ""
    single = text.replace("\n", " ").strip()
    if len(single) <= max_chars:
        return single
    return single[: max_chars - 3] + "..."


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
