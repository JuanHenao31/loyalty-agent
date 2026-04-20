"""Return the active card, points balance and expiration for a customer."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.guardrails import require_tool_access


class GetCustomerLoyaltyStatusArgs(BaseModel):
    customer_id: UUID = Field(description="UUID del cliente, obtenido antes con find_customer.")


@tool("get_customer_loyalty_status", args_schema=GetCustomerLoyaltyStatusArgs)
async def get_customer_loyalty_status(
    customer_id: UUID, config: Annotated[RunnableConfig, ""]
) -> dict:
    """Devuelve el estado de lealtad del cliente: id de tarjeta, saldo de puntos y expiración.

    Si el cliente no tiene tarjeta activa, devuelve `{"has_card": false}`.
    """
    ctx = require_tool_access("get_customer_loyalty_status", config)
    cards = await ctx.loyalty.list_cards(ctx.company_id, customer_id=customer_id)
    active = next((c for c in cards if c.status == "active"), None)
    if not active:
        return {"has_card": False, "cards": [{"id": str(c.id), "status": c.status} for c in cards]}
    return {
        "has_card": True,
        "card_id": str(active.id),
        "status": active.status,
        "current_points_balance": active.current_points_balance,
        "points_expire_at": active.points_expire_at.isoformat() if active.points_expire_at else None,
    }
