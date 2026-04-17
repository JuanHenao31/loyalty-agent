"""Domain and infrastructure exceptions."""


class LoyaltyAgentError(Exception):
    """Base error for the loyalty agent."""


class LoyaltyApiError(LoyaltyAgentError):
    """Upstream loyalty core returned an error."""

    def __init__(self, status_code: int, message: str, payload: dict | None = None):
        super().__init__(f"loyalty api {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload or {}


class AuthenticationError(LoyaltyAgentError):
    """Login against the loyalty core failed or token could not be refreshed."""


class NoBindingError(LoyaltyAgentError):
    """The chat identity has not been bound to a loyalty internal_user yet."""


class RoleForbiddenError(LoyaltyAgentError):
    """Internal user's role doesn't permit this action."""


class ConfirmationExpiredError(LoyaltyAgentError):
    """The pending confirmation has already expired."""


class GuardrailViolation(LoyaltyAgentError):
    """A guardrail blocked the agent from proceeding."""
