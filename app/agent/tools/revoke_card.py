"""Revoke a customer's loyalty card (SENSITIVE, business_owner+)."""

from typing import Annotated
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.tools._context import get_turn_context
from app.shared.exceptions import RoleForbiddenError


class RevokeCardArgs(BaseModel):
    card_id: UUID = Field(description="UUID de la tarjeta a revocar.")


@tool("revoke_card", args_schema=RevokeCardArgs)
async def revoke_card(card_id: UUID, config: Annotated[RunnableConfig, ""]) -> dict:
    """ACCIÓN SENSIBLE. Revoca la tarjeta del cliente (queda inutilizable).
    Solo `business_owner` o `platform_admin` pueden ejecutar esta acción."""
    ctx = get_turn_context(config)
    if ctx.role == "staff":
        raise RoleForbiddenError(
            "Tu rol (staff) no permite revocar tarjetas. Pide a un business_owner que lo haga."
        )
    card = await ctx.loyalty.revoke_card(
        ctx.company_id, card_id, as_user_token=ctx.user_access_token
    )
    return card.model_dump(mode="json")
