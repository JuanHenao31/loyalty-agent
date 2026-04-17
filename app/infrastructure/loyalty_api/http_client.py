"""Thin httpx wrapper that talks to the loyalty core.

Responsibilities:
- Injects Authorization headers chosen by the auth manager.
- Applies Idempotency-Key on mutation endpoints when provided.
- Normalizes non-2xx responses into LoyaltyApiError.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.domain.entities.loyalty import (
    CompanyAnalyticsSummary,
    Customer,
    LoyaltyCard,
    PointsTransaction,
    Reward,
    RewardRedemption,
)
from app.domain.ports.loyalty_service import LoyaltyServicePort
from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
from app.shared.exceptions import LoyaltyApiError

logger = logging.getLogger(__name__)


def build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.loyalty_api_base_url,
        timeout=settings.loyalty_api_timeout_seconds,
    )


class HttpLoyaltyServiceAdapter(LoyaltyServicePort):
    """Default LoyaltyServicePort implementation using the loyalty REST API."""

    def __init__(self, auth: LoyaltyAuthManager):
        self._auth = auth

    # --- Customers ---

    async def list_customers(
        self, company_id: UUID, *, search: str | None = None
    ) -> list[Customer]:
        data = await self._get(f"/api/v1/companies/{company_id}/customers")
        items = [Customer.model_validate(item) for item in data]
        if search:
            needle = search.lower().strip()
            items = [
                c
                for c in items
                if needle in f"{c.first_name} {c.last_name}".lower()
                or needle in c.email.lower()
                or (c.phone and needle in c.phone.lower())
            ]
        return items

    async def get_customer(self, company_id: UUID, customer_id: UUID) -> Customer:
        data = await self._get(
            f"/api/v1/companies/{company_id}/customers/{customer_id}"
        )
        return Customer.model_validate(data)

    async def create_customer_with_card(
        self,
        company_id: UUID,
        *,
        payload: dict,
        idempotency_key: str,
        as_user_token: str | None = None,
    ) -> dict:
        token = as_user_token or await self._auth.get_service_token()
        return await self._request(
            "POST",
            f"/api/v1/companies/{company_id}/customers/register-with-card",
            token=token,
            json=payload,
            extra_headers={"Idempotency-Key": idempotency_key},
        )

    # --- Loyalty cards ---

    async def list_cards(
        self, company_id: UUID, *, customer_id: UUID | None = None
    ) -> list[LoyaltyCard]:
        params: dict[str, Any] = {}
        if customer_id:
            params["customer_id"] = str(customer_id)
        data = await self._get(
            f"/api/v1/companies/{company_id}/loyalty-cards", params=params
        )
        return [LoyaltyCard.model_validate(item) for item in data]

    async def revoke_card(
        self, company_id: UUID, card_id: UUID, *, as_user_token: str
    ) -> LoyaltyCard:
        data = await self._request(
            "POST",
            f"/api/v1/companies/{company_id}/loyalty-cards/{card_id}/revoke",
            token=as_user_token,
        )
        return LoyaltyCard.model_validate(data)

    # --- Rewards ---

    async def list_rewards(
        self, company_id: UUID, *, status: str | None = "active"
    ) -> list[Reward]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        data = await self._get(
            f"/api/v1/companies/{company_id}/rewards", params=params
        )
        return [Reward.model_validate(item) for item in data]

    # --- Points ---

    async def earn_points(
        self,
        company_id: UUID,
        card_id: UUID,
        *,
        points: int,
        reason: str,
        idempotency_key: str,
        as_user_token: str,
    ) -> PointsTransaction:
        data = await self._request(
            "POST",
            f"/api/v1/companies/{company_id}/loyalty-cards/{card_id}/points/earn",
            token=as_user_token,
            json={"points": points, "reason": reason},
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        return PointsTransaction.model_validate(data)

    async def list_points_transactions(
        self, company_id: UUID, card_id: UUID
    ) -> list[PointsTransaction]:
        data = await self._get(
            f"/api/v1/companies/{company_id}/loyalty-cards/{card_id}/points-transactions"
        )
        return [PointsTransaction.model_validate(item) for item in data]

    # --- Redemptions ---

    async def redeem_reward(
        self,
        company_id: UUID,
        card_id: UUID,
        *,
        reward_id: UUID,
        reason: str | None,
        idempotency_key: str,
        as_user_token: str,
    ) -> RewardRedemption:
        body: dict[str, Any] = {"reward_id": str(reward_id)}
        if reason:
            body["reason"] = reason
        data = await self._request(
            "POST",
            f"/api/v1/companies/{company_id}/loyalty-cards/{card_id}/redeem",
            token=as_user_token,
            json=body,
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        return RewardRedemption.model_validate(data)

    async def list_redemptions(
        self, company_id: UUID, card_id: UUID
    ) -> list[RewardRedemption]:
        data = await self._get(
            f"/api/v1/companies/{company_id}/loyalty-cards/{card_id}/redemptions"
        )
        return [RewardRedemption.model_validate(item) for item in data]

    # --- Analytics ---

    async def company_analytics(self, company_id: UUID) -> CompanyAnalyticsSummary:
        data = await self._get(f"/api/v1/companies/{company_id}/analytics/summary")
        return CompanyAnalyticsSummary.model_validate(data)

    # --- Low-level helpers ---

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        token = await self._auth.get_service_token()
        return await self._request("GET", path, token=token, params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"}
        if extra_headers:
            headers.update(extra_headers)
        async with build_http_client() as client:
            resp = await client.request(
                method, path, headers=headers, json=json, params=params
            )
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = {"detail": resp.text}
            raise LoyaltyApiError(
                resp.status_code,
                payload.get("detail", resp.reason_phrase),
                payload,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()
