"""LoyaltyAuthManager: login, caching, refresh behavior."""

import time

import httpx
import pytest
import respx

from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
from app.shared.exceptions import AuthenticationError, LoyaltyApiError

BASE = "http://loyalty.test"


def _client_factory():
    return httpx.AsyncClient(base_url=BASE, timeout=5.0)


@respx.mock
async def test_service_token_is_cached_across_calls(monkeypatch):
    from app.infrastructure.loyalty_api import auth_manager as am
    monkeypatch.setattr(am.settings, "loyalty_agent_service_email", "svc@x.com")
    monkeypatch.setattr(am.settings, "loyalty_agent_service_password", "pw")

    login = respx.post(f"{BASE}/api/v1/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "AT1", "refresh_token": "RT1", "expires_in": 1800},
        )
    )
    auth = LoyaltyAuthManager(_client_factory)

    t1 = await auth.get_service_token()
    t2 = await auth.get_service_token()

    assert t1 == "AT1"
    assert t2 == "AT1"
    assert login.call_count == 1  # cached on second call


@respx.mock
async def test_service_token_refetched_after_expiry(monkeypatch):
    from app.infrastructure.loyalty_api import auth_manager as am
    monkeypatch.setattr(am.settings, "loyalty_agent_service_email", "svc@x.com")
    monkeypatch.setattr(am.settings, "loyalty_agent_service_password", "pw")

    login = respx.post(f"{BASE}/api/v1/auth/login").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"access_token": "A1", "refresh_token": "R1", "expires_in": 70},
            ),
            httpx.Response(
                200,
                json={"access_token": "A2", "refresh_token": "R2", "expires_in": 1800},
            ),
        ]
    )
    auth = LoyaltyAuthManager(_client_factory)
    assert await auth.get_service_token() == "A1"

    # Force-expire the cached token without waiting.
    auth._service_token.expires_at = time.time() - 1

    assert await auth.get_service_token() == "A2"
    assert login.call_count == 2


@respx.mock
async def test_service_token_raises_without_credentials(monkeypatch):
    from app.infrastructure.loyalty_api import auth_manager as am
    monkeypatch.setattr(am.settings, "loyalty_agent_service_email", "")
    monkeypatch.setattr(am.settings, "loyalty_agent_service_password", "")
    auth = LoyaltyAuthManager(_client_factory)
    with pytest.raises(AuthenticationError):
        await auth.get_service_token()


@respx.mock
async def test_user_token_uses_refresh_flow():
    respx.post(f"{BASE}/api/v1/auth/refresh").mock(
        return_value=httpx.Response(
            200, json={"access_token": "USER-AT", "expires_in": 1800}
        )
    )
    auth = LoyaltyAuthManager(_client_factory)
    token = await auth.get_user_token(cache_key="user:abc", refresh_token="RT-ABC")
    assert token == "USER-AT"


@respx.mock
async def test_login_failure_raises_loyalty_api_error(monkeypatch):
    from app.infrastructure.loyalty_api import auth_manager as am
    monkeypatch.setattr(am.settings, "loyalty_agent_service_email", "svc@x.com")
    monkeypatch.setattr(am.settings, "loyalty_agent_service_password", "wrong")
    respx.post(f"{BASE}/api/v1/auth/login").mock(
        return_value=httpx.Response(401, json={"detail": "invalid credentials"})
    )
    auth = LoyaltyAuthManager(_client_factory)
    with pytest.raises(LoyaltyApiError) as exc:
        await auth.get_service_token()
    assert exc.value.status_code == 401
