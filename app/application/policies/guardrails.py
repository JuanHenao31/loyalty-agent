"""Policy helpers (off-topic detection, rate checks, RBAC pre-checks).

Thin wrappers over app.agent.guardrails so the application layer can apply
them before calling the runtime without pulling in langchain types.
"""

from app.agent.guardrails import (
    SENSITIVE_TOOLS,
    looks_off_topic,
    require_tool_access,
    tool_allowed_for_role,
)

__all__ = [
    "SENSITIVE_TOOLS",
    "looks_off_topic",
    "require_tool_access",
    "tool_allowed_for_role",
]
