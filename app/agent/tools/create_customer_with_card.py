"""Create a new customer and issue the loyalty card in one idempotent call (SENSITIVE)."""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, EmailStr, Field

from app.agent.guardrails import require_tool_access
from app.shared.ids import derive_idempotency_key


class CreateCustomerWithCardArgs(BaseModel):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    marketing_consent: bool = False


@tool("create_customer_with_card", args_schema=CreateCustomerWithCardArgs)
async def create_customer_with_card(
    first_name: str,
    last_name: str,
    email: str,
    config: Annotated[RunnableConfig, ""],
    phone: str | None = None,
    marketing_consent: bool = False,
) -> dict:
    """ACCIÓN SENSIBLE. Crea un cliente nuevo en la empresa actual e inscribe una tarjeta de lealtad.
    Debe pedirse confirmación al usuario antes de ejecutarla."""
    ctx = require_tool_access("create_customer_with_card", config)
    idem = derive_idempotency_key(
        "create_customer_with_card",
        ctx.idempotency_seed,
        email.lower(),
    )
    return await ctx.loyalty.create_customer_with_card(
        ctx.company_id,
        payload={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "marketing_consent": marketing_consent,
        },
        idempotency_key=idem,
        as_user_token=ctx.user_access_token,
    )
