"""Normalized inbound message command produced by channel adapters."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InboundMessageCommand(BaseModel):
    """Channel-agnostic representation of a message arriving at the agent."""

    channel: Literal["telegram", "whatsapp", "web"]
    channel_user_id: str
    channel_message_id: str
    text: str
    received_at: datetime
    sender_display_name: str | None = None
    raw_payload: dict | None = None
