"""HttpLoyaltyServiceAdapter: header injection + error mapping."""

from uuid import uuid4

import httpx
import pytest
import respx

from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
from app.infrastructure.loyalty_api.http_client import HttpLoyaltyServiceAdapter
from app.shared.exceptions import LoyaltyApiError

BASE = "http://loyalty.test"


def _client_factory():
    return httpx.AsyncClient(base_url=BASE, timeout=5.0)


def _primed_auth(monkeypatch) -> LoyaltyAuthManager:
    from app.infrastructure.loyalty_api import auth_manager as am
    monkeypatch.setattr(am.settings, "loyalty_agent_service_email", "svc@x.com")
    monkeypatch.setattr(am.settings, "loyalty_agent_service_password", "pw")
    return LoyaltyAuthManager(_client_factory)


@respx.mock
async def test_list_customers_sends_service_bearer(monkeypatch):
    respx.post(f"{BASE}/api/v1/auth/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "SVC", "expires_in": 1800}
        )
    )
    company_id = uuid4()
    route = respx.get(f"{BASE}/api/v1/companies/{company_id}/customers").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid4()),
                    "company_id": str(company_id),
                    "first_name": "Laura",
                    "last_name": "Perez",
                    "email": "laura@x.com",
                    "phone": None,
                    "birth_date": None,
                    "external_customer_code": None,
                    "marketing_consent": False,
                    "status": "active",
                }
            ],
        )
    )
    adapter = HttpLoyaltyServiceAdapter(_primed_auth(monkeypatch))
    customers = await adapter.list_customers(company_id)
    assert len(customers) == 1
    assert customers[0].first_name == "Laura"
    assert route.calls.last.request.headers["authorization"] == "Bearer SVC"


@respx.mock
async def test_earn_points_injects_idempotency_key(monkeypatch):
    company_id = uuid4()
    card_id = uuid4()
    route = respx.post(
        f"{BASE}/api/v1/companies/{company_id}/loyalty-cards/{card_id}/points/earn"
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "company_id": str(company_id),
                "loyalty_card_id": str(card_id),
                "customer_id": str(uuid4()),
                "type": "earn",
                "points": 5,
                "reason": "corte",
                "balance_before": 0,
                "balance_after": 5,
                "created_at": "2026-04-17T10:00:00Z",
            },
        )
    )
    adapter = HttpLoyaltyServiceAdapter(_primed_auth(monkeypatch))
    tx = await adapter.earn_points(
        company_id,
        card_id,
        points=5,
        reason="corte",
        idempotency_key="IDEMP-123",
        as_user_token="USER-TOKEN",
    )
    assert tx.balance_after == 5
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer USER-TOKEN"
    assert req.headers["idempotency-key"] == "IDEMP-123"


@respx.mock
async def test_http_error_maps_to_loyalty_api_error(monkeypatch):
    company_id = uuid4()
    respx.post(f"{BASE}/api/v1/auth/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "SVC", "expires_in": 1800}
        )
    )
    respx.get(f"{BASE}/api/v1/companies/{company_id}/customers").mock(
        return_value=httpx.Response(403, json={"detail": "forbidden"})
    )
    adapter = HttpLoyaltyServiceAdapter(_primed_auth(monkeypatch))
    with pytest.raises(LoyaltyApiError) as exc:
        await adapter.list_customers(company_id)
    assert exc.value.status_code == 403
    assert "forbidden" in exc.value.message
