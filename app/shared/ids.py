"""ID helpers (UUID generation + idempotency key derivation)."""

import hashlib
import uuid


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def derive_idempotency_key(namespace: str, *parts: str) -> str:
    """Deterministic idempotency key for a (namespace, parts) tuple.

    The agent passes this as the Idempotency-Key header on mutation calls so
    that retries caused by channel redelivery don't duplicate points or
    redemptions.
    """
    hasher = hashlib.sha256()
    hasher.update(namespace.encode("utf-8"))
    for part in parts:
        hasher.update(b"\x1f")
        hasher.update(part.encode("utf-8"))
    return hasher.hexdigest()
