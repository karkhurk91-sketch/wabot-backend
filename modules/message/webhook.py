from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from modules.common.config import VERIFY_TOKEN
from modules.common.database import get_db
from modules.common.models import Organization, Conversation, Message
from modules.ai.processor import process_incoming_message
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
async def receive_webhook(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    logger.info(f"Webhook received: {body}")

    try:
        entry = body["entry"][0]
        for change in entry.get("changes", []):
            value = change.get("value", {})
            
            # Handle incoming messages
            if "messages" in value:
                msg_data = value["messages"][0]
                from_number = msg_data["from"]
                text = msg_data["text"]["body"]
                timestamp = int(msg_data["timestamp"])
                business_phone_number = value["metadata"]["display_phone_number"]
                whatsapp_msg_id = msg_data["id"]

                # Find organization
                org_res = await db.execute(
                    select(Organization.id).where(Organization.whatsapp_phone_number == business_phone_number)
                )
                org = org_res.scalar_one_or_none()
                if not org:
                    logger.warning(f"No organization for {business_phone_number}")
                    continue

                # Find or create conversation
                conv_stmt = select(Conversation).where(
                    Conversation.organization_id == org,
                    Conversation.customer_phone_number == from_number
                )
                conv = (await db.execute(conv_stmt)).scalar_one_or_none()
                if not conv:
                    conv = Conversation(
                        id=uuid.uuid4(),
                        organization_id=org,
                        customer_phone_number=from_number,
                        status="open",
                        reply_mode="ai",
                        started_at=datetime.utcnow(),
                        last_message_at=datetime.utcnow()
                    )
                    db.add(conv)
                    try:
                        await db.flush()
                        logger.info(f"Created conversation {conv.id} for {from_number}")
                    except IntegrityError:
                        await db.rollback()
                        conv = (await db.execute(conv_stmt)).scalar_one()
                else:
                    if conv.reply_mode is None:
                        conv.reply_mode = 'ai'

                # Save inbound message
                new_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    direction="inbound",
                    content=text,
                    is_ai_generated=False,
                    status="delivered",
                    whatsapp_message_id=whatsapp_msg_id,
                    created_at=datetime.utcnow()
                )
                db.add(new_msg)
                conv.last_message_at = datetime.utcnow()
                db.add(conv)
                await db.commit()

                # Schedule AI reply if in AI mode
                if conv.reply_mode == 'human':
                    logger.info(f"Conversation {conv.id} human mode - skip AI")
                else:
                    background_tasks.add_task(
                        process_incoming_message,
                        {
                            "from_number": from_number,
                            "text": text,
                            "timestamp": timestamp,
                            "org_id": str(org),
                            "conversation_id": str(conv.id)
                        }
                    )

            # Handle status updates (sent, delivered, read)
            if "statuses" in value:
                for status_update in value["statuses"]:
                    status = status_update["status"]  # 'sent', 'delivered', 'read'
                    recipient_id = status_update["recipient_id"]
                    whatsapp_msg_id = status_update.get("id")  # WhatsApp message ID
                    if not whatsapp_msg_id:
                        continue
                    # Find message in our DB by whatsapp_message_id
                    msg_res = await db.execute(
                        select(Message).where(Message.whatsapp_message_id == whatsapp_msg_id)
                    )
                    msg = msg_res.scalar_one_or_none()
                    if msg:
                        msg.status = status
                        msg.updated_at = datetime.utcnow()
                        await db.commit()
                        logger.info(f"Updated message {msg.id} status to {status}")
                    else:
                        logger.warning(f"Message not found for WhatsApp ID {whatsapp_msg_id}")

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        await db.rollback()

    return {"status": "ok"}