"""Main orchestrator: given an inbound message, run the agent and reply.

Flow:
1. Look up the channel identity binding (phone / chat_id → internal_user).
   If missing → reply with onboarding instructions and stop.
2. Load or create the session for that (channel, channel_user_id) pair.
3. Persist the inbound message.
4. If the text looks off-topic (cheap heuristic), record a guardrail event,
    reply with a scope reminder, and skip the LLM.
5. Fetch a fresh user access_token via the auth manager.
6. Build an AgentTurnContext and invoke the agent graph with a thread_id
    derived from the session_id (so the PostgresSaver checkpointer wires
    human-in-the-loop interrupts correctly). Tools enforce RBAC per role;
    a denial ends the turn with a guardrail audit row and a fixed user message.
7. Extract the assistant's final text and send it through the outbound adapter.

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

from app.agent.runtime import AgentRuntime, render_system_prompt
from app.agent.tools._context import AgentTurnContext
from app.application.dto.inbound import InboundMessageCommand
from app.application.policies.guardrails import looks_off_topic
from app.core.branding import GUARDRAIL_OFF_TOPIC_MESSAGE, ONBOARDING_MESSAGE
from app.core.config import settings
from app.core.logging import preview_for_log
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
from app.shared.exceptions import GuardrailViolation

logger = logging.getLogger(__name__)


@dataclass
class ProcessInboundMessage:
    session: AsyncSession
    runtime: AgentRuntime
    auth: LoyaltyAuthManager
    loyalty: LoyaltyServicePort
    outbound: OutboundChannelPort

    async def handle(self, cmd: InboundMessageCommand) -> None:
        logger.info(
            "inbound handle start channel=%s user=%s text_len=%d preview=%r",
            cmd.channel,
            cmd.channel_user_id,
            len(cmd.text),
            preview_for_log(cmd.text, 80),
        )
        binding = await self._find_binding(cmd.channel, cmd.channel_user_id)
        if not binding:
            logger.info(
                "inbound no binding channel=%s user=%s -> onboarding message",
                cmd.channel,
                cmd.channel_user_id,
            )
            await self.outbound.send_text(cmd.channel_user_id, ONBOARDING_MESSAGE)
            return

        agent_session = await self._get_or_create_session(binding, cmd)
        logger.info(
            "inbound session_id=%s company_id=%s internal_user_id=%s",
            agent_session.id,
            binding.company_id,
            binding.internal_user_id,
        )
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

        if looks_off_topic(cmd.text):
            logger.info(
                "inbound off_topic guardrail session_id=%s -> skip LLM",
                agent_session.id,
            )
            await audit.record_guardrail(
                session_id=agent_session.id,
                event_type="off_topic",
                message="Inbound text matched off-topic heuristics; agent not invoked.",
                metadata={"channel": cmd.channel},
            )
            await self._reply_and_touch_session(agent_session, cmd, GUARDRAIL_OFF_TOPIC_MESSAGE)
            return

        logger.info("inbound resolving user token internal_user_id=%s", binding.internal_user_id)
        user_token = await self._resolve_user_token(binding)
        logger.info("inbound user token ok (len=%d)", len(user_token))

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
        logger.info(
            "inbound invoking graph thread_id=%s recursion_limit=%s",
            config["configurable"]["thread_id"],
            config.get("recursion_limit"),
        )
        try:
            result = await self.runtime.graph.ainvoke({"messages": messages}, config)
        except GuardrailViolation as exc:
            logger.warning(
                "inbound graph stopped tool_rbac_denied session_id=%s metadata=%s",
                agent_session.id,
                exc.audit_metadata,
            )
            await audit.record_guardrail(
                session_id=agent_session.id,
                event_type="tool_rbac_denied",
                message=str(exc),
                metadata=exc.audit_metadata,
            )
            await self._reply_and_touch_session(agent_session, cmd, exc.user_message)
            return

        raw_msgs = result.get("messages", [])
        logger.info(
            "inbound graph done session_id=%s state_messages=%d",
            agent_session.id,
            len(raw_msgs) if isinstance(raw_msgs, list) else -1,
        )
        reply_text = self._extract_final_text(result)
        logger.info(
            "inbound assistant_reply chars=%d preview=%r",
            len(reply_text),
            preview_for_log(reply_text, 120),
        )
        await self._reply_and_touch_session(agent_session, cmd, reply_text)

    async def _reply_and_touch_session(
        self, agent_session: AgentSession, cmd: InboundMessageCommand, reply_text: str
    ) -> None:
        self.session.add(
            AgentMessage(
                session_id=agent_session.id,
                role="assistant",
                message_text=reply_text,
            )
        )
        agent_session.last_activity_at = datetime.now(timezone.utc)
        logger.info(
            "inbound outbound send channel_user_id=%s chars=%d",
            cmd.channel_user_id,
            len(reply_text),
        )
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
