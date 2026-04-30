import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from modules.common.database import get_db
from modules.common.models import Conversation, Message, Tag, ConversationTag, ConversationNote
from modules.auth.jwt import get_current_user
from modules.common.logger import get_logger
from modules.message.sender import send_whatsapp_text

logger = get_logger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

# ---------- Schemas ----------
class MessageCreate(BaseModel):
    text: str
    sender_type: str  # 'agent'

class NoteCreate(BaseModel):
    note: str

class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#4F46E5"

# ---------- Conversation List ----------
@router.get("")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(403, "Organization not found")

    stmt = select(Conversation).where(
        Conversation.organization_id == org_id
    ).order_by(Conversation.last_message_at.desc())
    result = await db.execute(stmt)
    convs = result.scalars().all()

    output = []
    for c in convs:
        last_msg_result = await db.execute(
            select(Message).where(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc()).limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()
        output.append({
            "id": c.id,
            "customer_phone_number": c.customer_phone_number,
            "customer_name": c.customer_name or "",
            "last_message": last_msg.content if last_msg else None,
            "last_message_at": c.last_message_at,
            "status": c.status,
            "lead_score": c.lead_score,
            "reply_mode": c.reply_mode,
            "unread_count": 0,
        })
    return output

# ---------- Messages ----------
@router.get("/{conv_id}/messages")
async def get_messages(
    conv_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stmt = select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------- Send message (agent) ----------
@router.post("/{conv_id}/send")
async def send_message(
    conv_id: UUID,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Verify conversation
    conv = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.organization_id == current_user["org_id"]
        )
    )
    conv = conv.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Create message record (status = 'sent' initially)
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        direction="outbound",
        message_type="text",
        content=data.text,
        is_ai_generated=False,
        human_agent_id=current_user.get("user_id"),
        status="sent",
        created_at=datetime.utcnow()
    )
    db.add(msg)
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id)
        .values(last_message_at=datetime.utcnow())
    )
    await db.commit()

    # Actually send via WhatsApp
    success, wamid = await send_whatsapp_text(
        to_number=conv.customer_phone_number,
        text=data.text,
        org_id=str(conv.organization_id)
    )
    if success:
        msg.whatsapp_message_id = wamid
        await db.commit()

    if not success:
        logger.error(f"Failed to send WhatsApp message to {conv.customer_phone_number}")
    else:
        # The message status will be updated by webhook when delivery receipt arrives
        pass

    return {"status": "sent", "message_id": msg.id}

# ---------- Notes & Tags (unchanged from your original) ----------
# ... (keep your existing notes and tags endpoints – they are fine)
# ---------- Notes ----------
@router.get("/{conv_id}/notes")
async def get_notes(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stmt = select(ConversationNote).where(ConversationNote.conversation_id == conv_id).order_by(ConversationNote.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{conv_id}/notes")
async def add_note(
    conv_id: UUID,
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    note = ConversationNote(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        agent_id=current_user.get("user_id"),
        note=data.note,
        created_at=datetime.utcnow()
    )
    db.add(note)
    await db.commit()
    return note

@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await db.execute(delete(ConversationNote).where(ConversationNote.id == note_id))
    await db.commit()
    return {"status": "deleted"}

# ---------- Tags (global) ----------
@router.get("/tags")
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stmt = select(Tag).where(Tag.organization_id == current_user["org_id"]).order_by(Tag.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/tags")
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    tag = Tag(
        id=uuid.uuid4(),
        organization_id=current_user["org_id"],
        name=data.name,
        color=data.color
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag

# ---------- Conversation-specific tags ----------
@router.get("/{conv_id}/tags")
async def get_conv_tags(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stmt = select(Tag).join(ConversationTag).where(ConversationTag.conversation_id == conv_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{conv_id}/tags/{tag_id}")
async def attach_tag(
    conv_id: UUID,
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Verify tag belongs to org
    tag = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.organization_id == current_user["org_id"])
    )
    if not tag.scalar_one_or_none():
        raise HTTPException(404, "Tag not found")
    ct = ConversationTag(conversation_id=conv_id, tag_id=tag_id)
    db.add(ct)
    await db.commit()
    return {"status": "attached"}

@router.delete("/{conv_id}/tags/{tag_id}")
async def detach_tag(
    conv_id: UUID,
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await db.execute(
        delete(ConversationTag).where(
            ConversationTag.conversation_id == conv_id,
            ConversationTag.tag_id == tag_id
        )
    )
    await db.commit()
    return {"status": "detached"}

# ---------- Toggle AI/Human mode ----------
@router.patch("/{conv_id}/mode")
async def toggle_mode(
    conv_id: UUID,
    mode: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if mode not in ('ai', 'human'):
        raise HTTPException(400, "Mode must be 'ai' or 'human'")
    await db.execute(
        update(Conversation).where(Conversation.id == conv_id).values(reply_mode=mode)
    )
    await db.commit()
    return {"reply_mode": mode}