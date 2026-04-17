"""Abstract port for talking to the loyalty core.

The agent's tools depend on this port, not on the HTTP client directly, so
implementations can be swapped in tests or for future transports (gRPC, etc.).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.loyalty import (
    CompanyAnalyticsSummary,
    Customer,
    LoyaltyCard,
    PointsTransaction,
    Reward,
    RewardRedemption,
)


class LoyaltyServicePort(ABC):
    # --- Customers ---
    @abstractmethod
    async def list_customers(
        self, company_id: UUID, *, search: str | None = None
    ) -> list[Customer]:
        ...

    @abstractmethod
    async def get_customer(self, company_id: UUID, customer_id: UUID) -> Customer:
        ...

    @abstractmethod
    async def create_customer_with_card(
        self,
        company_id: UUID,
        *,
        payload: dict,
        idempotency_key: str,
        as_user_token: str | None = None,
    ) -> dict:
        ...

    # --- Loyalty cards ---
    @abstractmethod
    async def list_cards(
        self, company_id: UUID, *, customer_id: UUID | None = None
    ) -> list[LoyaltyCard]:
        ...

    @abstractmethod
    async def revoke_card(
        self, company_id: UUID, card_id: UUID, *, as_user_token: str
    ) -> LoyaltyCard:
        ...

    # --- Rewards ---
    @abstractmethod
    async def list_rewards(
        self, company_id: UUID, *, status: str | None = "active"
    ) -> list[Reward]:
        ...

    # --- Points ---
    @abstractmethod
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
        ...

    @abstractmethod
    async def list_points_transactions(
        self, company_id: UUID, card_id: UUID
    ) -> list[PointsTransaction]:
        ...

    # --- Redemptions ---
    @abstractmethod
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
        ...

    @abstractmethod
    async def list_redemptions(
        self, company_id: UUID, card_id: UUID
    ) -> list[RewardRedemption]:
        ...

    # --- Analytics ---
    @abstractmethod
    async def company_analytics(self, company_id: UUID) -> CompanyAnalyticsSummary:
        ...
