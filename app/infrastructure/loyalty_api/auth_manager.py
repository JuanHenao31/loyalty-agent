"""Hybrid auth manager for the loyalty core.

Service account tokens (for read-only tools) are cached in-process.
Per-user tokens are derived from encrypted refresh tokens stored in
channel_identity_bindings and refreshed on demand so that mutations are
attributed to the real internal_user in the loyalty audit trail.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from app.core.config import settings
from app.shared.exceptions import AuthenticationError, LoyaltyApiError

logger = logging.getLogger(__name__)


@dataclass
class _CachedToken:
    access_token: str
    refresh_token: str | None
    expires_at: float  # unix epoch seconds


class LoyaltyAuthManager:
    """Owns token lifecycle against the loyalty core.

    Instances are safe to share across tool invocations; an async lock
    serializes concurrent refreshes for a given cache key.
    """

    def __init__(self, client_factory: Callable[[], httpx.AsyncClient]):
        self._client_factory = client_factory
        self._service_token: _CachedToken | None = None
        self._user_tokens: dict[str, _CachedToken] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # --- Service account (read-only tools) ---

    async def get_service_token(self) -> str:
        if self._service_token and not self._is_expired(self._service_token):
            return self._service_token.access_token
        lock = self._locks.setdefault("__service__", asyncio.Lock())
        async with lock:
            if self._service_token and not self._is_expired(self._service_token):
                return self._service_token.access_token
            if not settings.loyalty_agent_service_email or not settings.loyalty_agent_service_password:
                raise AuthenticationError(
                    "LOYALTY_AGENT_SERVICE_EMAIL / LOYALTY_AGENT_SERVICE_PASSWORD not configured"
                )
            self._service_token = await self._login(
                email=settings.loyalty_agent_service_email,
                password=settings.loyalty_agent_service_password,
            )
            return self._service_token.access_token

    # --- Per-user (mutation tools) ---

    async def get_user_token(self, *, cache_key: str, refresh_token: str) -> str:
        cached = self._user_tokens.get(cache_key)
        if cached and not self._is_expired(cached):
            return cached.access_token
        lock = self._locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._user_tokens.get(cache_key)
            if cached and not self._is_expired(cached):
                return cached.access_token
            refreshed = await self._refresh(refresh_token)
            self._user_tokens[cache_key] = refreshed
            return refreshed.access_token

    async def login_user(self, *, email: str, password: str) -> _CachedToken:
        """Used during onboarding to obtain the initial refresh token for a user."""
        return await self._login(email=email, password=password)

    # --- Internals ---

    async def _login(self, *, email: str, password: str) -> _CachedToken:
        async with self._client_factory() as client:
            try:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": password},
                )
            except httpx.HTTPError as exc:
                raise AuthenticationError(f"loyalty login transport error: {exc}") from exc
        return self._parse_token_response(resp, action="login")

    async def _refresh(self, refresh_token: str) -> _CachedToken:
        async with self._client_factory() as client:
            try:
                resp = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": refresh_token},
                )
            except httpx.HTTPError as exc:
                raise AuthenticationError(f"loyalty refresh transport error: {exc}") from exc
        token = self._parse_token_response(resp, action="refresh")
        # /auth/refresh returns only access_token; preserve the original refresh for reuse
        token.refresh_token = token.refresh_token or refresh_token
        return token

    def _parse_token_response(self, resp: httpx.Response, *, action: str) -> _CachedToken:
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = {"detail": resp.text}
            raise LoyaltyApiError(resp.status_code, f"{action} failed", payload)
        body = resp.json()
        access = body.get("access_token")
        if not access:
            raise AuthenticationError(f"{action} response missing access_token")
        expires_in = int(body.get("expires_in") or 1500)
        # Refresh 60s before expiry to avoid races.
        expires_at = time.time() + max(60, expires_in - 60)
        return _CachedToken(
            access_token=access,
            refresh_token=body.get("refresh_token"),
            expires_at=expires_at,
        )

    @staticmethod
    def _is_expired(token: _CachedToken) -> bool:
        return token.expires_at <= time.time()

    def invalidate_user(self, cache_key: str) -> None:
        self._user_tokens.pop(cache_key, None)
