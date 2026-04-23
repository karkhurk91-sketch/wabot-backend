# modules/ai/processor.py
import asyncio
from modules.ai.agent import get_agent_for_user_compat
from modules.message.sender import send_whatsapp_text, send_whatsapp_template
from modules.ai.lead_capture import create_lead
from modules.common.database import sync_engine
from sqlalchemy import text
from modules.common.logger import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)

def has_recent_customer_message(customer_phone: str, org_id: str) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 1 FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.customer_phone_number = :phone
                AND c.organization_id = :org_id
                AND m.direction = 'inbound'
                AND m.created_at > :cutoff
                LIMIT 1
            """),
            {"phone": customer_phone, "org_id": org_id, "cutoff": cutoff}
        )
        return result.fetchone() is not None

def get_lead_capture_enabled(org_id: str) -> bool:
    try:
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enable_lead_capture FROM ai_configurations WHERE organization_id = :org_id"),
                {"org_id": org_id}
            )
            row = result.fetchone()
            return row[0] if row else True
    except Exception:
        return True

async def process_incoming_message(message: dict):
    """
    This async function processes the message and sends a reply.
    It will be called as a background task (FastAPI supports async tasks).
    """
    user_id = message["from_number"]
    user_text = message["text"]
    org_id = message.get("org_id")

    logger.info(f"Processing message from {user_id}: {user_text}")

    recent = has_recent_customer_message(user_id, org_id)
    lead_capture_enabled = get_lead_capture_enabled(org_id)

    agent = get_agent_for_user_compat(user_id, org_id)
    ai_response = agent.predict(user_text)  # This is synchronous, but it's fine
    logger.info(f"AI response: {ai_response[:200]}")

    # Await the async send functions
    if recent:
        success = await send_whatsapp_text(to_number=user_id, text=ai_response)
    else:
        success = await send_whatsapp_template(to_number=user_id, template_name="hello_world", language_code="en")

    if success:
        logger.info(f"Reply sent to {user_id}")
    else:
        logger.error(f"Failed to send reply to {user_id}")

    if lead_capture_enabled and org_id:
        keywords = ["buy", "price", "interested", "purchase", "cost", "quote", "want", "order"]
        if any(kw in user_text.lower() for kw in keywords):
            await create_lead(org_id, user_id, user_text[:100])  # create_lead is async
            logger.info(f"Lead captured for {user_id}")