"""In-loop guardrails applied before/after the LLM turn."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.core.branding import GUARDRAIL_RBAC_DENIED
from app.shared.exceptions import GuardrailViolation

if TYPE_CHECKING:
    from app.agent.tools._context import AgentTurnContext

Role = Literal["platform_admin", "business_owner", "staff"]

# Tools that require elevated permissions (business_owner or platform_admin)
BUSINESS_OWNER_TOOLS = {"revoke_card"}

# Tools that mutate state — these are interrupt-before in the agent graph
SENSITIVE_TOOLS = {
    "create_customer_with_card",
    "add_points",
    "redeem_reward",
    "revoke_card",
}


def tool_allowed_for_role(tool_name: str, role: Role) -> bool:
    if role == "platform_admin":
        return True
    if tool_name in BUSINESS_OWNER_TOOLS and role == "staff":
        return False
    return True


def _normalize_role(role: str) -> Role:
    if role in ("platform_admin", "business_owner", "staff"):
        return role  # type: ignore[return-value]
    return "staff"


def require_tool_access(tool_name: str, config: dict | None) -> "AgentTurnContext":
    """Resolve turn context and enforce RBAC before any loyalty tool runs."""
    from app.agent.tools._context import get_turn_context

    ctx = get_turn_context(config)
    eff_role = _normalize_role(ctx.role)
    if not tool_allowed_for_role(tool_name, eff_role):
        raise GuardrailViolation(
            f"tool {tool_name} denied for role {eff_role}",
            user_message=GUARDRAIL_RBAC_DENIED,
            audit_metadata={"tool": tool_name, "role": eff_role},
        )
    return ctx


OFFTOPIC_HINTS = (
    "política",
    "religión",
    "chiste",
    "horóscopo",
    "receta",
    "programar código",
)


def looks_off_topic(user_text: str) -> bool:
    lower = user_text.lower()
    return any(hint in lower for hint in OFFTOPIC_HINTS)
