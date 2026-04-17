"""Per-turn context injected into tools via LangGraph RunnableConfig.

Tools should NEVER receive company_id / user_token as LLM arguments, because
the model could hallucinate them. Instead, the ProcessInboundMessage use case
builds an `AgentTurnContext` when starting the run and passes it through
`config["configurable"]`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.ports.loyalty_service import LoyaltyServicePort

Role = Literal["platform_admin", "business_owner", "staff"]


@dataclass
class AgentTurnContext:
    company_id: UUID
    internal_user_id: UUID
    role: Role
    session_id: UUID
    loyalty: LoyaltyServicePort
    user_access_token: str
    # Seed used to derive per-action idempotency keys so retries are safe.
    idempotency_seed: str


def get_turn_context(config: dict) -> AgentTurnContext:
    configurable = config.get("configurable") if config else None
    if not configurable or "turn_context" not in configurable:
        raise RuntimeError("AgentTurnContext missing from RunnableConfig.configurable")
    ctx = configurable["turn_context"]
    if not isinstance(ctx, AgentTurnContext):
        raise RuntimeError("RunnableConfig.configurable['turn_context'] has wrong type")
    return ctx
