"""Static knowledge about the loyalty program (no loyalty API call)."""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ExplainLoyaltyPolicyArgs(BaseModel):
    topic: str = Field(
        description="Tema de la política: 'expiracion', 'redencion', 'tarjeta', 'general'."
    )


@tool("explain_loyalty_policy", args_schema=ExplainLoyaltyPolicyArgs)
async def explain_loyalty_policy(
    topic: str, config: Annotated[RunnableConfig, ""]
) -> str:
    """Devuelve la explicación estática del tema de política solicitado."""
    topic = topic.lower().strip()
    answers = {
        "expiracion": "Los puntos expiran después del número de meses configurado por la empresa (`points_expiration_months`). Cada vez que se suman puntos, la fecha de expiración se reinicia hacia adelante.",
        "redencion": "Para redimir, el cliente debe tener una tarjeta activa y suficientes puntos para cubrir `points_required` de la recompensa. La operación es atómica: si falla, no se deduce nada.",
        "tarjeta": "Cada cliente puede tener solo una tarjeta activa a la vez. Las tarjetas pasan por estados: pending → sent → active → (revoked | expired).",
        "general": "Lumi opera sobre el microservicio loyalty de Techapoli: clientes, tarjetas, puntos, recompensas, redenciones. Toda acción sensible requiere confirmación humana explícita.",
    }
    return answers.get(topic, answers["general"])
