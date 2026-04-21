"""WhatsApp Cloud API webhook — verify GET + POST inbound with HMAC signature."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.application.dto.inbound import InboundMessageCommand
from app.core.config import settings
from app.core.logging import preview_for_log
from app.entrypoints.webhooks._dispatch import run_agent_turn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("")
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
) -> PlainTextResponse:
    """Meta's webhook verification handshake."""
    if hub_mode != "subscribe" or hub_verify_token != settings.whatsapp_verify_token:
        raise HTTPException(status_code=403, detail="invalid verify token")
    return PlainTextResponse(hub_challenge)


@router.post("")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    raw = await request.body()
    _verify_signature(request.headers.get("x-hub-signature-256"), raw)

    payload = await request.json()
    # Meta wraps messages in entry[*].changes[*].value.messages[*]
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            contacts = {c.get("wa_id"): c for c in value.get("contacts", [])}
            for msg in value.get("messages", []) or []:
                if msg.get("type") != "text":
                    continue
                wa_id = msg.get("from")
                if not wa_id:
                    continue
                text = (msg.get("text") or {}).get("body", "")
                contact = contacts.get(wa_id) or {}
                display = (contact.get("profile") or {}).get("name")

                cmd = InboundMessageCommand(
                    channel="whatsapp",
                    channel_user_id=wa_id,
                    channel_message_id=msg.get("id", ""),
                    text=text,
                    received_at=datetime.now(timezone.utc),
                    sender_display_name=display,
                    raw_payload=payload,
                )
                logger.info(
                    "whatsapp webhook accepted wa_id=%s msg_id=%s text_len=%d preview=%r",
                    wa_id,
                    msg.get("id", ""),
                    len(text),
                    preview_for_log(text, 80),
                )
                background_tasks.add_task(run_agent_turn, request, cmd)
    return {"ok": True}


def _verify_signature(signature_header: str | None, raw_body: bytes) -> None:
    if not settings.whatsapp_app_secret:
        # Signature validation disabled — allowed only if the secret is unset
        # (useful for local/ngrok testing); in production the secret MUST be set.
        return
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="missing signature")
    expected = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature_header.split("=", 1)[1]
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="invalid signature")
