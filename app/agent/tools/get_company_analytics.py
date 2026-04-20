"""Return loyalty analytics for the user's company."""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel

from app.agent.guardrails import require_tool_access


class GetCompanyAnalyticsArgs(BaseModel):
    pass


@tool("get_company_analytics", args_schema=GetCompanyAnalyticsArgs)
async def get_company_analytics(config: Annotated[RunnableConfig, ""]) -> dict:
    """Devuelve métricas agregadas del programa de la empresa:
    total de clientes, tarjetas activas, puntos emitidos/redimidos,
    recompensas creadas/redimidas, promedio de puntos por tarjeta y tasa de redención."""
    ctx = require_tool_access("get_company_analytics", config)
    summary = await ctx.loyalty.company_analytics(ctx.company_id)
    return summary.model_dump()
