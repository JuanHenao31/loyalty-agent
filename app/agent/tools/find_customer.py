"""Search for a customer by name, email, or phone within the user's company."""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.guardrails import require_tool_access


class FindCustomerArgs(BaseModel):
    query: str = Field(description="Nombre, email o teléfono (o parte) del cliente a buscar.")


@tool("find_customer", args_schema=FindCustomerArgs)
async def find_customer(query: str, config: Annotated[RunnableConfig, ""]) -> list[dict]:
    """Busca clientes en la empresa del usuario actual por nombre, email o teléfono.

    Devuelve una lista de hasta 10 coincidencias con id, nombre, email, teléfono y status.
    """
    ctx = require_tool_access("find_customer", config)
    customers = await ctx.loyalty.list_customers(ctx.company_id, search=query)
    return [
        {
            "id": str(c.id),
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "phone": c.phone,
            "status": c.status,
        }
        for c in customers[:10]
    ]
