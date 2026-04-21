"""Shared helpers for turning a raw webhook payload into an agent run.

The webhook handlers themselves return 200 immediately and schedule the
actual processing in a background task, so the channel won't retry due to
timeout.
"""

from __future__ import annotations

import logging

from fastapi import Request

from app.application.dto.inbound import InboundMessageCommand
from app.application.use_cases.process_inbound_message import ProcessInboundMessage
from app.core.branding import USER_PROCESSING_ERROR
from app.core.database import AsyncSessionLocal
from app.core.logging import preview_for_log
from app.infrastructure.loyalty_api.http_client import HttpLoyaltyServiceAdapter
from app.infrastructure.messaging.telegram_adapter import TelegramOutboundAdapter
from app.infrastructure.messaging.whatsapp_adapter import WhatsAppOutboundAdapter

logger = logging.getLogger(__name__)


def _outbound_for(channel: str):
    if channel == "telegram":
        return TelegramOutboundAdapter()
    if channel == "whatsapp":
        return WhatsAppOutboundAdapter()
    raise ValueError(f"unsupported channel: {channel}")


async def run_agent_turn(request: Request, cmd: InboundMessageCommand) -> None:
    """Background-task entrypoint. Pulls shared runtime+auth from app.state."""
    runtime = request.app.state.agent_runtime
    auth = request.app.state.loyalty_auth
    outbound = _outbound_for(cmd.channel)
    logger.info(
        "agent_turn start channel=%s user=%s text_len=%d preview=%r",
        cmd.channel,
        cmd.channel_user_id,
        len(cmd.text),
        preview_for_log(cmd.text, 80),
    )
    try:
        async with AsyncSessionLocal() as session:
            try:
                loyalty = HttpLoyaltyServiceAdapter(auth)
                uc = ProcessInboundMessage(
                    session=session,
                    runtime=runtime,
                    auth=auth,
                    loyalty=loyalty,
                    outbound=outbound,
                )
                await uc.handle(cmd)
                await session.commit()
                logger.info(
                    "agent_turn committed channel=%s user=%s",
                    cmd.channel,
                    cmd.channel_user_id,
                )
            except Exception:
                await session.rollback()
                raise
    except Exception:
        logger.exception("agent turn failed for channel=%s user=%s", cmd.channel, cmd.channel_user_id)
        try:
            await outbound.send_text(cmd.channel_user_id, USER_PROCESSING_ERROR)
        except Exception:
            logger.exception("failed to notify user of error")
