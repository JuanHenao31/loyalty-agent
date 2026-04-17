"""List rewards available to the customer's company, flagged by affordability."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.tools._context import get_turn_context


class GetCustomerRewardsArgs(BaseModel):
    customer_id: UUID | None = Field(
        default=None,
        description="Opcional: UUID del cliente para marcar recompensas alcanzables.",
    )


@tool("get_customer_rewards", args_schema=GetCustomerRewardsArgs)
async def get_customer_rewards(
    config: Annotated[RunnableConfig, ""],
    customer_id: UUID | None = None,
) -> list[dict]:
    """Lista las recompensas activas de la empresa. Si se pasa customer_id, marca cuáles puede redimir con su saldo actual."""
    ctx = get_turn_context(config)
    rewards = await ctx.loyalty.list_rewards(ctx.company_id, status="active")
    balance = None
    if customer_id is not None:
        cards = await ctx.loyalty.list_cards(ctx.company_id, customer_id=customer_id)
        active = next((c for c in cards if c.status == "active"), None)
        balance = active.current_points_balance if active else None
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "points_required": r.points_required,
            "affordable": (balance is not None and balance >= r.points_required),
        }
        for r in rewards
    ]
