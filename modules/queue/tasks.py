import asyncio
from modules.queue.producer import celery_app
from modules.ai.agent import get_agent_for_user_compat
from modules.message.sender import send_whatsapp_template, send_whatsapp_text
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

@celery_app.task(name="process_incoming_message", bind=True, max_retries=3)
def process_incoming_message(self, message: dict):
    user_id = message["from_number"]
    user_text = message["text"]
    org_id = message.get("org_id")

    logger.info(f"Processing message from {user_id}: {user_text}")

    recent = has_recent_customer_message(user_id, org_id)
    lead_capture_enabled = get_lead_capture_enabled(org_id)

    agent = get_agent_for_user_compat(user_id, org_id)
    ai_response = agent.predict(user_text)
    logger.info(f"AI response: {ai_response[:200]}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def send():
        success = False
        if recent:
            success = await send_whatsapp_text(to_number=user_id, text=ai_response)
        else:
            # First message – send a template
            success = await send_whatsapp_template(
                to_number=user_id,
                template_name="hello_world",
                language_code="en"
            )
        if success:
            logger.info(f"Reply sent to {user_id}")
        else:
            logger.error(f"Failed to send reply to {user_id}")

        # Lead capture (keyword detection)
        if lead_capture_enabled and org_id:
            keywords = ["buy", "price", "interested", "purchase", "cost", "quote", "want", "order"]
            if any(kw in user_text.lower() for kw in keywords):
                await create_lead(org_id, user_id, user_text[:100])
                logger.info(f"Lead captured for {user_id}")

    try:
        loop.run_until_complete(send())
    except Exception as e:
        logger.error(f"Task failed for {user_id}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    finally:
        loop.close()