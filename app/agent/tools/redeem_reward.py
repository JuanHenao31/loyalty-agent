"""Redeem a reward from a customer's active card (SENSITIVE)."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.guardrails import require_tool_access
from app.shared.exceptions import LoyaltyApiError
from app.shared.ids import derive_idempotency_key


class RedeemRewardArgs(BaseModel):
    customer_id: UUID = Field(description="UUID del cliente.")
    reward_id: UUID = Field(description="UUID de la recompensa a redimir.")
    reason: str | None = Field(default=None, max_length=500)


@tool("redeem_reward", args_schema=RedeemRewardArgs)
async def redeem_reward(
    customer_id: UUID,
    reward_id: UUID,
    config: Annotated[RunnableConfig, ""],
    reason: str | None = None,
) -> dict:
    """ACCIÓN SENSIBLE. Canjea una recompensa del cliente, deduciendo los puntos necesarios.
    Requiere confirmación humana previa."""
    ctx = require_tool_access("redeem_reward", config)
    cards = await ctx.loyalty.list_cards(ctx.company_id, customer_id=customer_id)
    active = next((c for c in cards if c.status == "active"), None)
    if not active:
        raise LoyaltyApiError(
            404, "El cliente no tiene una tarjeta activa; no se puede redimir."
        )
    idem = derive_idempotency_key(
        "redeem_reward",
        ctx.idempotency_seed,
        str(active.id),
        str(reward_id),
    )
    red = await ctx.loyalty.redeem_reward(
        ctx.company_id,
        active.id,
        reward_id=reward_id,
        reason=reason,
        idempotency_key=idem,
        as_user_token=ctx.user_access_token,
    )
    return red.model_dump(mode="json")
