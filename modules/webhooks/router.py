# modules/webhooks/router.py
from fastapi import APIRouter, Request, HTTPException, Query
from modules.channels.factory import ChannelFactory
from modules.common.database import sync_engine
from sqlalchemy import text
from modules.common.models import Conversation, Message
from modules.common.logger import get_logger
import uuid
from datetime import datetime

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Helper to map incoming webhook to organization (simplified)
async def get_org_id_from_webhook(channel: str, request: Request) -> str:
    if channel == "telegram":
        # Telegram passes bot token in URL or header – implement lookup
        pass
    elif channel == "facebook":
        # Look up by page_id from payload
        data = await request.json()
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            with sync_engine.connect() as conn:
                row = conn.execute(
                    text("SELECT organization_id FROM organization_channels WHERE channel_type = 'facebook' AND config->>'page_id' = :page_id"),
                    {"page_id": page_id}
                ).fetchone()
                if row:
                    return row[0]
    return None

@router.post("/{channel_type}")
async def channel_webhook(channel_type: str, request: Request):
    org_id = await get_org_id_from_webhook(channel_type, request)
    if not org_id:
        return {"status": "ignored"}

    with sync_engine.connect() as conn:
        row = conn.execute(
            text("SELECT config FROM organization_channels WHERE organization_id = :org_id AND channel_type = :channel"),
            {"org_id": org_id, "channel": channel_type}
        ).fetchone()
    if not row:
        return {"status": "channel not configured"}

    adapter = ChannelFactory.get_adapter(channel_type, org_id, row.config)
    internal_msg = await adapter.handle_webhook(request)
    if not internal_msg:
        return {"status": "no message"}

    # Store message (simplified – you can reuse existing conversation logic)
    return {"status": "ok"}

@router.get("/facebook")
async def verify_facebook_webhook(
    hub_mode: str = Query(None),
    hub_verify_token: str = Query(None),
    hub_challenge: int = Query(None)
):
    # Replace with your own verify token (must match what you enter in Meta dashboard)
    FACEBOOK_VERIFY_TOKEN = "myWhatsApp2026"
    if hub_mode == "subscribe" and hub_verify_token == FACEBOOK_VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")


@router.get("/instagram")
async def verify_instagram_webhook(
    hub_mode: str = Query(None),
    hub_verify_token: str = Query(None),
    hub_challenge: int = Query(None)
):
    # Use a verify token (must match what you set in Meta dashboard for Instagram)
    INSTAGRAM_VERIFY_TOKEN = "myWhatsApp2026"  # change as needed
    if hub_mode == "subscribe" and hub_verify_token == INSTAGRAM_VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")