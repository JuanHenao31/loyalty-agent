"""WhatsApp Cloud API sender (OutboundChannelPort)."""

import logging

import httpx

from app.core.config import settings
from app.domain.ports.outbound_channel import OutboundChannelPort

logger = logging.getLogger(__name__)


class WhatsAppOutboundAdapter(OutboundChannelPort):
    channel_name = "whatsapp"

    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        graph_version: str | None = None,
    ):
        self._access_token = access_token or settings.whatsapp_access_token
        self._phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self._graph_version = graph_version or settings.whatsapp_graph_version

    async def send_text(self, to: str, text: str) -> None:
        if not self._access_token or not self._phone_number_id:
            logger.warning("WhatsApp credentials incomplete; dropping outbound message")
            return
        url = f"https://graph.facebook.com/{self._graph_version}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error(
                "whatsapp sendMessage failed: %s %s", resp.status_code, resp.text
            )
