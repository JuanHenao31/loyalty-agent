"""Telegram webhook — validates secret header, normalizes Update, dispatches."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.application.dto.inbound import InboundMessageCommand
from app.core.config import settings
from app.core.logging import preview_for_log
from app.entrypoints.webhooks._dispatch import run_agent_turn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/telegram", tags=["webhooks"])


@router.post("")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            logger.warning("telegram webhook rejected: secret token mismatch")
            raise HTTPException(status_code=401, detail="invalid secret token")

    payload = await request.json()
    message = payload.get("message") or payload.get("edited_message")
    if not message or "text" not in message:
        logger.debug("telegram webhook ignored: non-text or empty update")
        return {"ok": True}

    chat_id = str(message["chat"]["id"])
    text = message["text"]
    message_id = str(message.get("message_id", ""))
    display = message["chat"].get("first_name") or message["chat"].get("username")

    cmd = InboundMessageCommand(
        channel="telegram",
        channel_user_id=chat_id,
        channel_message_id=message_id,
        text=text,
        received_at=datetime.now(timezone.utc),
        sender_display_name=display,
        raw_payload=payload,
    )
    logger.info(
        "telegram webhook accepted chat_id=%s msg_id=%s text_len=%d preview=%r",
        chat_id,
        message_id,
        len(text),
        preview_for_log(text, 80),
    )
    background_tasks.add_task(run_agent_turn, request, cmd)
    return {"ok": True}
