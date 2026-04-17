"""Shared test fixtures and env setup (runs before any test module is imported)."""

import os

# Deterministic Fernet key for tests (32 bytes base64). Set BEFORE importing
# app.core.* modules so the settings singleton picks it up.
os.environ.setdefault(
    "REFRESH_TOKEN_ENCRYPTION_KEY", "xP8y9RJZiW2s8WzYxw7xsU7NnZT3w4m2nw3lFq3n-eY="
)
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("LOYALTY_API_BASE_URL", "http://loyalty.test")
