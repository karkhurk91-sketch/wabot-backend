from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from modules.common.config import VERIFY_TOKEN
from modules.common.database import get_db
from modules.common.models import Organization, Conversation, Message
from modules.ai.processor import process_incoming_message
from modules.ai.rule_processor import get_rule_reply
from modules.message.sender import send_whatsapp_text
from modules.common.logger import get_logger
import uuid
from datetime import datetime

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["WhatsApp"])

@router.get("")
async def verify_webhook(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: int = None
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Log raw request arrival
    logger.info("Webhook POST request received")
    try:
        body = await request.json()
        logger.info(f"Webhook body: {body}")
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {"status": "error", "detail": "Invalid JSON"}

    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Handle incoming messages
        if "messages" in value:
            msg_data = value["messages"][0]
            from_number = msg_data["from"]
            text = msg_data["text"]["body"]
            timestamp = int(msg_data["timestamp"])
            business_phone_number = value["metadata"]["display_phone_number"]

            # Find organization
            result = await db.execute(
                select(Organization.id, Organization.business_type)
                .where(Organization.whatsapp_phone_number == business_phone_number)
            )
            row = result.first()
            if not row:
                logger.warning(f"No organization found for WhatsApp number: {business_phone_number}")
                return {"status": "ignored", "reason": "unknown_whatsapp_number"}
            org_id, business_type = row

            # Find or create conversation
            conv_stmt = select(Conversation).where(
                Conversation.organization_id == org_id,
                Conversation.customer_phone_number == from_number
            )
            conv = (await db.execute(conv_stmt)).scalar_one_or_none()

            if not conv:
                conv = Conversation(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    customer_phone_number=from_number,
                    status="open",
                    reply_mode="ai",
                    started_at=datetime.utcnow(),
                    last_message_at=datetime.utcnow(),
                    rule_state={}
                )
                db.add(conv)
                try:
                    await db.flush()
                    logger.info(f"Created new conversation for {from_number} under org {org_id}")
                except IntegrityError:
                    await db.rollback()
                    conv = (await db.execute(conv_stmt)).scalar_one()
                    logger.info(f"Retrieved existing conversation {conv.id} for {from_number}")
            else:
                if conv.reply_mode is None:
                    conv.reply_mode = 'ai'
                logger.info(f"Using existing conversation {conv.id} for {from_number}")

            # Save incoming message
            new_message = Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                direction="inbound",
                content=text,
                is_ai_generated=False,
                status="delivered",
                created_at=datetime.utcnow()
            )
            db.add(new_message)
            conv.last_message_at = datetime.utcnow()
            db.add(conv)
            await db.commit()

            # -------------------------------------------------
            # RULE MODE HANDLING
            # -------------------------------------------------
            if conv.reply_mode == 'rule':
                reply, _ = await get_rule_reply(str(org_id), str(conv.id), text)
                if reply:
                    success, wamid = await send_whatsapp_text(to_number=from_number, text=reply, org_id=str(org_id))
                    if success:
                        out_msg = Message(
                            id=uuid.uuid4(),
                            conversation_id=conv.id,
                            direction="outbound",
                            content=reply,
                            is_ai_generated=False,
                            status="sent",
                            created_at=datetime.utcnow(),
                            whatsapp_message_id=wamid
                        )
                        db.add(out_msg)
                        conv.last_message_at = datetime.utcnow()
                        await db.commit()
                        logger.info(f"Rule-based reply sent to {from_number}")
                        return {"status": "ok"}
                else:
                    # No rule matched – fallback to AI mode (optional)
                    logger.info(f"No rule matched for {from_number}, falling back to AI mode")
                    conv.reply_mode = 'ai'
                    await db.commit()
                    # Continue to AI processing below

            # -------------------------------------------------
            # HUMAN or AI MODE
            # -------------------------------------------------
            if conv.reply_mode == 'human':
                logger.info(f"Conversation {conv.id} in human mode – skipping AI reply")
                return {"status": "ok"}
            else:
                # AI mode (or fallback from rule)
                background_tasks.add_task(
                    process_incoming_message,
                    {
                        "from_number": from_number,
                        "text": text,
                        "timestamp": timestamp,
                        "org_id": str(org_id),
                        "conversation_id": str(conv.id)
                    }
                )
                logger.info(f"Scheduled AI processing for message from {from_number}")

        # Handle status updates (optional)
        if "statuses" in value:
            for status_update in value["statuses"]:
                logger.info(f"Status update: {status_update}")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        await db.rollback()

    return {"status": "ok"}