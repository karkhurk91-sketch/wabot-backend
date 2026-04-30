import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text
from modules.ai.agent import get_agent_for_user_compat
from modules.message.sender import send_whatsapp_text, send_whatsapp_template
from modules.ai.lead_capture import create_lead
from modules.common.database import sync_engine, AsyncSessionLocal  # <-- fixed import
from modules.common.models import Conversation, Message
from modules.common.logger import get_logger

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
    Called from webhook with a dict containing: from_number, text, timestamp, org_id, conversation_id.
    """
    conversation_id = message.get("conversation_id")
    user_id = message["from_number"]
    user_text = message["text"]
    org_id = message.get("org_id")
    timestamp = message.get("timestamp")

    if not conversation_id:
        logger.error("Missing conversation_id in message dict")
        return

    await _process_and_reply(
        conversation_id=conversation_id,
        customer_phone=user_id,
        customer_message=user_text,
        org_id=org_id,
        timestamp=timestamp
    )

async def _process_and_reply(
    conversation_id: str,
    customer_phone: str,
    customer_message: str,
    org_id: str,
    timestamp: int = None
):
    logger.info(f"Processing message from {customer_phone}: {customer_message}")

    recent = has_recent_customer_message(customer_phone, org_id)
    lead_capture_enabled = get_lead_capture_enabled(org_id)

    agent = get_agent_for_user_compat(customer_phone, org_id)
    ai_response = agent.predict(customer_message)
    logger.info(f"AI response: {ai_response[:200]}")

    lead_data = getattr(agent, '_pending_lead', None)
    if lead_data and lead_data.get('lead') and lead_capture_enabled:
        interest = lead_data.get('interest', customer_message[:100])
        service = lead_data.get('service')
        score = lead_data.get('score', 70)
        await create_lead(org_id, customer_phone, interest, service=service, lead_score=score)
        logger.info(f"Lead created for {customer_phone} (service: {service}, score: {score})")

    # Send reply
    if recent:
        success, wamid = await send_whatsapp_text(to_number=customer_phone, text=ai_response, org_id=str(org_id))
    else:
        success = await send_whatsapp_template(
            to_number=customer_phone,
            template_name="hello",
            language_code="en",
            category="UTILITY",
            org_id=str(org_id)
        )

    if not success:
        logger.error(f"Failed to send reply to {customer_phone}")
        return

    logger.info(f"Reply sent to {customer_phone}")

    # Store the AI reply in DB
    async with AsyncSessionLocal() as db:
        try:
            ai_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                direction="outbound",
                message_type="text",
                content=ai_response,
                is_ai_generated=True,
                created_at=datetime.utcnow()
            )
            db.add(ai_msg)

            await db.execute(
                text("UPDATE conversations SET last_message_at = NOW() WHERE id = :conv_id"),
                {"conv_id": conversation_id}
            )
            await db.commit()
            logger.info(f"Stored AI reply for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to store AI reply in DB: {e}")
            await db.rollback()