from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from modules.common.database import get_db
from modules.common.models import Lead
from modules.auth.jwt import get_current_user
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/leads", tags=["Leads"])

class LeadUpdate(BaseModel):
    status: str

@router.get("")
async def list_leads(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user.get("org_id")
    query = select(Lead).order_by(Lead.created_at.desc())
    if org_id:
        query = query.where(Lead.organization_id == org_id)
    result = await db.execute(query)
    leads = result.scalars().all()
    return leads

@router.patch("/{lead_id}")
async def update_lead(
    lead_id: UUID,
    update: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user.get("org_id")
    # Find lead, ensuring it belongs to the organization
    query = select(Lead).where(Lead.id == lead_id)
    if org_id:
        query = query.where(Lead.organization_id == org_id)
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = update.status
    await db.commit()
    return {"status": "updated"}