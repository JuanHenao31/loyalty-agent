"""In-loop guardrails applied before/after the LLM turn."""

from __future__ import annotations

from typing import Literal

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
