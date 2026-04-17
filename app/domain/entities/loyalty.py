"""Pydantic DTOs mirroring the loyalty core API surface (subset used by the agent)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class Customer(BaseModel):
    id: UUID
    company_id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    birth_date: date | None = None
    external_customer_code: str | None = None
    marketing_consent: bool = False
    status: Literal["active", "inactive"] = "active"


class LoyaltyCard(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    status: Literal["pending", "sent", "active", "inactive", "revoked", "expired"]
    current_points_balance: int
    points_expire_at: datetime | None = None
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    customer_email: str | None = None


class Reward(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str | None = None
    points_required: int = Field(gt=0)
    status: Literal["active", "inactive"]
    expires_at: datetime | None = None


class PointsTransaction(BaseModel):
    id: UUID
    company_id: UUID
    loyalty_card_id: UUID
    customer_id: UUID
    type: Literal["earn", "redeem"]
    points: int
    reason: str | None = None
    balance_before: int
    balance_after: int
    created_at: datetime


class RewardRedemption(BaseModel):
    id: UUID
    company_id: UUID
    loyalty_card_id: UUID
    customer_id: UUID
    reward_id: UUID
    points_consumed: int
    reason: str | None = None
    created_at: datetime


class CompanyAnalyticsSummary(BaseModel):
    total_customers: int = 0
    active_cards: int = 0
    total_points_issued: int = 0
    total_points_redeemed: int = 0
    total_rewards_created: int = 0
    total_rewards_redeemed: int = 0
    avg_points_per_card: float = 0.0
    redemption_rate: float = 0.0


class LoyaltyAuthTokens(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int


class LoyaltyUserContext(BaseModel):
    """Decoded subset of the loyalty JWT claims used in-memory by the agent."""

    internal_user_id: UUID
    company_id: UUID | None
    role: Literal["platform_admin", "business_owner", "staff"]
    email: EmailStr
