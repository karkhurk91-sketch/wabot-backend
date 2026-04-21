from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from modules.common.database import get_db
from modules.common.models import Organization, User, Customer, Conversation, Lead
from modules.auth.jwt import get_current_super_admin, get_password_hash
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# ---------- Pydantic models ----------
class OrganizationApprove(BaseModel):
    status: str  # active, suspended

class OrganizationCreate(BaseModel):
    name: str
    business_type: Optional[str] = None
    gst: Optional[str] = None
    description: Optional[str] = None
    admin_email: str
    admin_password: str
    # WhatsApp credentials (optional during creation)
    whatsapp_phone_number: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    wat_org: Optional[str] = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    gst: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[str] = None
    whatsapp_phone_number: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    wat_org: Optional[str] = None


# ---------- Helper to get admin email ----------
async def get_org_admin_email(org_id: UUID, db: AsyncSession) -> Optional[str]:
    result = await db.execute(
        select(User.email).where(User.organization_id == org_id, User.role == "org_admin")
    )
    return result.scalar_one_or_none()

# ---------- Existing endpoints (enhanced) ----------
@router.get("/organizations")
async def list_organizations(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    query = select(Organization)
    if status:
        query = query.where(Organization.status == status)
    result = await db.execute(query.order_by(Organization.created_at.desc()))
    orgs = result.scalars().all()
    
    # Enrich with admin email (optional)
    enriched = []
    for org in orgs:
        admin_email = await get_org_admin_email(org.id, db)
        enriched.append({
            "id": org.id,
            "name": org.name,
            "business_type": org.business_type,
            "whatsapp_phone_number": org.whatsapp_phone_number,
            "whatsapp_phone_number_id": org.whatsapp_phone_number_id,
            "whatsapp_business_account_id": org.whatsapp_business_account_id,
            "status": org.status,
            "plan": org.plan,
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "admin_email": admin_email,
            "wat_org": org.wat_org
        })
    return enriched

@router.post("/organizations")
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    # Check if email already used
    result = await db.execute(select(User).where(User.email == org_data.admin_email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "Admin email already registered")
    
    # Create organization
    new_org = Organization(
        name=org_data.name,
        business_type=org_data.business_type,
        status="active",
        settings={"gst": org_data.gst, "description": org_data.description},
        whatsapp_phone_number=org_data.whatsapp_phone_number,
        whatsapp_phone_number_id=org_data.whatsapp_phone_number_id,
        whatsapp_access_token=org_data.whatsapp_access_token,
        whatsapp_business_account_id=org_data.whatsapp_business_account_id,
        wat_org= org_data.wat_org
    )
    db.add(new_org)
    await db.flush()
    
    # Create admin user
    hashed = get_password_hash(org_data.admin_password)
    new_user = User(
        email=org_data.admin_email,
        password_hash=hashed,
        full_name=org_data.name,
        role="org_admin",
        organization_id=new_org.id,
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_org)
    return new_org

@router.patch("/organizations/{org_id}/status")
async def update_org_status(
    org_id: UUID,
    data: OrganizationApprove,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    stmt = update(Organization).where(Organization.id == org_id).values(status=data.status)
    await db.execute(stmt)
    await db.commit()
    return {"status": "updated"}

@router.put("/organizations/{org_id}")
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    # Fetch existing organization
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    
    # Update only provided fields
    update_data = data.dict(exclude_unset=True)
    # Handle settings (gst, description) stored as JSON
    if "gst" in update_data or "description" in update_data:
        current_settings = org.settings or {}
        if "gst" in update_data:
            current_settings["gst"] = update_data.pop("gst")
        if "description" in update_data:
            current_settings["description"] = update_data.pop("description")
        org.settings = current_settings
    
    for key, value in update_data.items():
        setattr(org, key, value)
    
    await db.commit()
    return {"status": "updated"}

@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    # Delete associated users first (cascade should handle, but explicit)
    await db.execute(delete(User).where(User.organization_id == org_id))
    await db.execute(delete(Organization).where(Organization.id == org_id))
    await db.commit()
    return {"status": "deleted"}

@router.get("/organizations/{org_id}")
async def get_organization_details(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    org = await db.execute(select(Organization).where(Organization.id == org_id))
    org_obj = org.scalar_one_or_none()
    if not org_obj:
        raise HTTPException(404, "Organization not found")
    
    # Get counts
    customers = await db.execute(select(func.count(Customer.id)).where(Customer.organization_id == org_id, Customer.deleted_at.is_(None)))
    conversations = await db.execute(select(func.count(Conversation.id)).where(Conversation.organization_id == org_id))
    leads = await db.execute(select(func.count(Lead.id)).where(Lead.organization_id == org_id))
    
    admin_email = await get_org_admin_email(org_id, db)
    
    return {
        "organization": {
            "id": org_obj.id,
            "name": org_obj.name,
            "business_type": org_obj.business_type,
            "whatsapp_phone_number": org_obj.whatsapp_phone_number,
            "whatsapp_phone_number_id": org_obj.whatsapp_phone_number_id,
            "whatsapp_business_account_id": org_obj.whatsapp_business_account_id,
            "status": org_obj.status,
            "plan": org_obj.plan,
            "settings": org_obj.settings,
            "created_at": org_obj.created_at.isoformat() if org_obj.created_at else None,
            "admin_email": admin_email,
            "wat_org": org.wat_org
        },
        "stats": {
            "customers": customers.scalar() or 0,
            "conversations": conversations.scalar() or 0,
            "leads": leads.scalar() or 0
        }
    }

@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_super_admin)
):
    total_orgs = (await db.execute(select(func.count(Organization.id)))).scalar()
    total_customers = (await db.execute(select(func.count(Customer.id)).where(Customer.deleted_at.is_(None)))).scalar()
    total_conversations = (await db.execute(select(func.count(Conversation.id)))).scalar()
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar()
    return {
        "totalOrganizations": total_orgs or 0,
        "totalCustomers": total_customers or 0,
        "totalConversations": total_conversations or 0,
        "totalLeads": total_leads or 0
    }