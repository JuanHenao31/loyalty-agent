"""Add points to a customer's active loyalty card (SENSITIVE)."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.guardrails import require_tool_access
from app.shared.exceptions import LoyaltyApiError
from app.shared.ids import derive_idempotency_key


class AddPointsArgs(BaseModel):
    customer_id: UUID = Field(description="UUID del cliente.")
    points: int = Field(gt=0, description="Puntos a sumar (entero positivo).")
    reason: str = Field(min_length=1, max_length=500, description="Motivo legible de la operación.")


@tool("add_points", args_schema=AddPointsArgs)
async def add_points(
    customer_id: UUID,
    points: int,
    reason: str,
    config: Annotated[RunnableConfig, ""],
) -> dict:
    """ACCIÓN SENSIBLE. Suma puntos a la tarjeta activa del cliente. Requiere confirmación humana previa."""
    ctx = require_tool_access("add_points", config)
    cards = await ctx.loyalty.list_cards(ctx.company_id, customer_id=customer_id)
    active = next((c for c in cards if c.status == "active"), None)
    if not active:
        raise LoyaltyApiError(
            404,
            "El cliente no tiene una tarjeta activa. Crea o activa una tarjeta antes de sumar puntos.",
        )
    idem = derive_idempotency_key(
        "add_points",
        ctx.idempotency_seed,
        str(active.id),
        str(points),
        reason,
    )
    tx = await ctx.loyalty.earn_points(
        ctx.company_id,
        active.id,
        points=points,
        reason=reason,
        idempotency_key=idem,
        as_user_token=ctx.user_access_token,
    )
    return tx.model_dump(mode="json")
