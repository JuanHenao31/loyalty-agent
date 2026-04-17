"""Postgres-backed AuditPort."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.audit import AuditPort
from app.infrastructure.persistence.models import AgentAuditLog, GuardrailEvent


class PostgresAuditAdapter(AuditPort):
    def __init__(self, session: AsyncSession):
        self._session = session

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
        self._session.add(
            AgentAuditLog(
                company_id=company_id,
                internal_user_id=internal_user_id,
                session_id=session_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_json=metadata,
            )
        )

    async def record_guardrail(
        self,
        *,
        session_id: UUID,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        self._session.add(
            GuardrailEvent(
                session_id=session_id,
                event_type=event_type,
                message=message,
                metadata_json=metadata,
            )
        )
