"""Symmetric encryption for refresh tokens stored at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256). The key is loaded from
`REFRESH_TOKEN_ENCRYPTION_KEY` (32-byte base64).
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(RuntimeError):
    pass


def _get_cipher() -> Fernet:
    key = settings.refresh_token_encryption_key
    if not key:
        raise EncryptionError(
            "REFRESH_TOKEN_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError(f"Invalid REFRESH_TOKEN_ENCRYPTION_KEY: {exc}") from exc


def encrypt_token(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    try:
        return _get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Refresh token decryption failed") from exc
