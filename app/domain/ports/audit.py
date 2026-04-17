"""Audit port — writes to agent_audit_logs and guardrail_events."""

from abc import ABC, abstractmethod
from uuid import UUID


class AuditPort(ABC):
    @abstractmethod
    async def record_action(
        self,
        *,
        company_id: UUID,
        internal_user_id: UUID,
        session_id: UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def record_guardrail(
        self,
        *,
        session_id: UUID,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        ...
