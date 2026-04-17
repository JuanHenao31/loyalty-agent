"""Telegram Bot API sender (OutboundChannelPort)."""

import logging

import httpx

from app.core.config import settings
from app.domain.ports.outbound_channel import OutboundChannelPort

logger = logging.getLogger(__name__)


class TelegramOutboundAdapter(OutboundChannelPort):
    channel_name = "telegram"

    def __init__(self, bot_token: str | None = None):
        self._bot_token = bot_token or settings.telegram_bot_token

    async def send_text(self, to: str, text: str) -> None:
        if not self._bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured; dropping outbound message")
            return
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": to, "text": text})
        if resp.status_code >= 400:
            logger.error("telegram sendMessage failed: %s %s", resp.status_code, resp.text)
