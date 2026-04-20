"""Return the customer's recent earn / redeem movements."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.guardrails import require_tool_access


class GetCustomerHistoryArgs(BaseModel):
    customer_id: UUID = Field(description="UUID del cliente.")
    limit: int = Field(default=10, ge=1, le=50, description="Máximo de movimientos a devolver.")


@tool("get_customer_history", args_schema=GetCustomerHistoryArgs)
async def get_customer_history(
    customer_id: UUID, config: Annotated[RunnableConfig, ""], limit: int = 10
) -> list[dict]:
    """Devuelve los últimos movimientos de puntos (earn / redeem) del cliente.

    Si el cliente no tiene tarjeta activa, devuelve lista vacía.
    """
    ctx = require_tool_access("get_customer_history", config)
    cards = await ctx.loyalty.list_cards(ctx.company_id, customer_id=customer_id)
    active = next((c for c in cards if c.status == "active"), None)
    if not active:
        return []
    txs = await ctx.loyalty.list_points_transactions(ctx.company_id, active.id)
    txs_sorted = sorted(txs, key=lambda t: t.created_at, reverse=True)[:limit]
    return [
        {
            "type": t.type,
            "points": t.points,
            "reason": t.reason,
            "balance_after": t.balance_after,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs_sorted
    ]
