from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.common.database import get_db
from modules.common.models import Conversation
from modules.auth.jwt import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user.get("org_id")
    query = select(Conversation).order_by(Conversation.last_message_at.desc())
    if org_id:
        query = query.where(Conversation.organization_id == org_id)
    result = await db.execute(query)
    convs = result.scalars().all()
    return [{
        "id": c.id,
        "customer_phone": c.customer_phone_number,
        "organization_name": None,   # optional, could fetch from organizations table
        "last_message": None,        # could join with messages table
        "status": c.status,
        "lead_score": c.lead_score
    } for c in convs]