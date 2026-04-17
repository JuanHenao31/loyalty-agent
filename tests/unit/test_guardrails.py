"""Role-gating and sensitive-tool policy."""

from app.agent.guardrails import SENSITIVE_TOOLS, tool_allowed_for_role


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
