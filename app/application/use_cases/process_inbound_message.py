"""Main orchestrator: given an inbound message, run the agent and reply.

Flow:
1. Look up the channel identity binding (phone / chat_id → internal_user).
   If missing → reply with onboarding instructions and stop.
2. Load or create the session for that (channel, channel_user_id) pair.
3. Persist the inbound message.
4. Fetch a fresh user access_token via the auth manager.
5. Build an AgentTurnContext and invoke the agent graph with a thread_id
   derived from the session_id (so the PostgresSaver checkpointer wires
   human-in-the-loop interrupts correctly).
6. Extract the assistant's final text and send it through the outbound adapter.

This use case does NOT handle confirmation resumption yet — that lives in a
sibling use case (ConfirmAction) that re-runs the same thread after the user
replies "sí" / "confirmo".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts.system import POLICY_KNOWLEDGE, SYSTEM_PROMPT
from app.agent.runtime import AgentRuntime, render_system_prompt
from app.agent.tools._context import AgentTurnContext
from app.application.dto.inbound import InboundMessageCommand
from app.core.config import settings
from app.core.security import decrypt_token
from app.domain.ports.loyalty_service import LoyaltyServicePort
from app.domain.ports.outbound_channel import OutboundChannelPort
from app.infrastructure.audit.postgres_audit import PostgresAuditAdapter
from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
from app.infrastructure.persistence.models import (
    AgentMessage,
    AgentSession,
    ChannelIdentityBinding,
)

logger = logging.getLogger(__name__)

ONBOARDING_MESSAGE = (
    "Hola. Este chat aún no está vinculado a un usuario de Techapoli Loyalty. "
    "Un administrador debe registrar tu número/usuario antes de que pueda ayudarte. "
    "Contacta al dueño del negocio para completar el registro."
)


@dataclass
class ProcessInboundMessage:
    session: AsyncSession
    runtime: AgentRuntime
    auth: LoyaltyAuthManager
    loyalty: LoyaltyServicePort
    outbound: OutboundChannelPort

    async def handle(self, cmd: InboundMessageCommand) -> None:
        binding = await self._find_binding(cmd.channel, cmd.channel_user_id)
        if not binding:
            await self.outbound.send_text(cmd.channel_user_id, ONBOARDING_MESSAGE)
            return

        agent_session = await self._get_or_create_session(binding, cmd)
        inbound_msg = AgentMessage(
            session_id=agent_session.id,
            role="user",
            message_text=cmd.text,
            raw_payload_json=cmd.raw_payload,
        )
        self.session.add(inbound_msg)
        await self.session.flush()

        audit = PostgresAuditAdapter(self.session)
        await audit.record_action(
            company_id=binding.company_id,
            internal_user_id=binding.internal_user_id,
            session_id=agent_session.id,
            action="inbound_message",
            metadata={"channel": cmd.channel, "message_id": cmd.channel_message_id},
        )

        user_token = await self._resolve_user_token(binding)

        turn_ctx = AgentTurnContext(
            company_id=binding.company_id,
            internal_user_id=binding.internal_user_id,
            role=binding.internal_user_role,  # type: ignore[arg-type]
            session_id=agent_session.id,
            loyalty=self.loyalty,
            user_access_token=user_token,
            idempotency_seed=str(agent_session.id),
        )

        system_prompt = render_system_prompt(
            company_id=str(binding.company_id),
            internal_user_id=str(binding.internal_user_id),
            role=binding.internal_user_role,
            user_display_name=cmd.sender_display_name or binding.internal_user_email,
        )

        config = {
            "configurable": {
                "thread_id": str(agent_session.id),
                "turn_context": turn_ctx,
            },
            "recursion_limit": settings.agent_max_tool_iterations * 2,
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": cmd.text},
        ]
        result = await self.runtime.graph.ainvoke({"messages": messages}, config)

        reply_text = self._extract_final_text(result)
        self.session.add(
            AgentMessage(
                session_id=agent_session.id,
                role="assistant",
                message_text=reply_text,
            )
        )
        agent_session.last_activity_at = datetime.now(timezone.utc)

        await self.outbound.send_text(cmd.channel_user_id, reply_text)

    # --- helpers ---

    async def _find_binding(
        self, channel: str, channel_user_id: str
    ) -> ChannelIdentityBinding | None:
        result = await self.session.execute(
            select(ChannelIdentityBinding).where(
                ChannelIdentityBinding.channel == channel,
                ChannelIdentityBinding.channel_user_id == channel_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_create_session(
        self, binding: ChannelIdentityBinding, cmd: InboundMessageCommand
    ) -> AgentSession:
        ttl = timedelta(hours=settings.agent_memory_ttl_hours)
        cutoff = datetime.now(timezone.utc) - ttl
        result = await self.session.execute(
            select(AgentSession).where(
                AgentSession.channel == cmd.channel,
                AgentSession.channel_user_id == cmd.channel_user_id,
                AgentSession.status == "active",
                AgentSession.last_activity_at >= cutoff,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        new_session = AgentSession(
            id=uuid4(),
            company_id=binding.company_id,
            internal_user_id=binding.internal_user_id,
            channel=cmd.channel,
            channel_user_id=cmd.channel_user_id,
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        self.session.add(new_session)
        await self.session.flush()
        return new_session

    async def _resolve_user_token(self, binding: ChannelIdentityBinding) -> str:
        refresh = decrypt_token(binding.encrypted_refresh_token)
        cache_key = f"user:{binding.internal_user_id}"
        return await self.auth.get_user_token(cache_key=cache_key, refresh_token=refresh)

    @staticmethod
    def _extract_final_text(result: dict) -> str:
        messages = result.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                return content
        return "(sin respuesta del agente)"
