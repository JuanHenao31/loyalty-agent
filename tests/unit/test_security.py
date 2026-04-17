"""Fernet round-trip for refresh-token encryption."""

import pytest

from app.core.security import EncryptionError, decrypt_token, encrypt_token


def test_roundtrip_preserves_plaintext():
    plaintext = "eyJhbGciOiJIUzI1NiJ9.some.refresh.token"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_tampered_ciphertext_raises():
    ciphertext = encrypt_token("hello")
    tampered = ciphertext[:-2] + "AA"
    with pytest.raises(EncryptionError):
        decrypt_token(tampered)
