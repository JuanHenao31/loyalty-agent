"""Role-gating and sensitive-tool policy."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.agent.guardrails import (
    SENSITIVE_TOOLS,
    looks_off_topic,
    require_tool_access,
    tool_allowed_for_role,
)
from app.agent.tools._context import AgentTurnContext
from app.shared.exceptions import GuardrailViolation


def test_sensitive_tools_cover_mutations():
    assert "add_points" in SENSITIVE_TOOLS
    assert "redeem_reward" in SENSITIVE_TOOLS
    assert "create_customer_with_card" in SENSITIVE_TOOLS
    assert "revoke_card" in SENSITIVE_TOOLS
    # Read-only tools must NOT be in the sensitive set.
    assert "find_customer" not in SENSITIVE_TOOLS
    assert "get_customer_loyalty_status" not in SENSITIVE_TOOLS


def test_staff_cannot_revoke_card():
    assert tool_allowed_for_role("revoke_card", "staff") is False


def test_business_owner_can_revoke_card():
    assert tool_allowed_for_role("revoke_card", "business_owner") is True


def test_platform_admin_can_do_anything():
    assert tool_allowed_for_role("revoke_card", "platform_admin") is True
    assert tool_allowed_for_role("add_points", "platform_admin") is True


def test_staff_can_still_add_points():
    # Staff has permission to earn/redeem for regular customer flows.
    assert tool_allowed_for_role("add_points", "staff") is True
    assert tool_allowed_for_role("redeem_reward", "staff") is True


def test_looks_off_topic_detects_configured_hints():
    assert looks_off_topic("cuéntame un chiste") is True
    assert looks_off_topic("POLÍTICA internacional") is True
    assert looks_off_topic("busca cliente Juan") is False


def test_require_tool_access_blocks_staff_revoke_card():
    ctx = AgentTurnContext(
        company_id=uuid4(),
        internal_user_id=uuid4(),
        role="staff",
        session_id=uuid4(),
        loyalty=MagicMock(),
        user_access_token="x",
        idempotency_seed="s",
    )
    config = {"configurable": {"turn_context": ctx}}
    with pytest.raises(GuardrailViolation) as ei:
        require_tool_access("revoke_card", config)
    assert "revoke_card" in str(ei.value)
    assert ei.value.audit_metadata.get("tool") == "revoke_card"


def test_require_tool_access_allows_owner_revoke_card():
    ctx = AgentTurnContext(
        company_id=uuid4(),
        internal_user_id=uuid4(),
        role="business_owner",
        session_id=uuid4(),
        loyalty=MagicMock(),
        user_access_token="x",
        idempotency_seed="s",
    )
    config = {"configurable": {"turn_context": ctx}}
    out = require_tool_access("revoke_card", config)
    assert out is ctx
