from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from modules.common.database import get_db
from modules.common.models import Organization, User
from modules.auth.jwt import get_current_user, hash_password, verify_password
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])

# ---------- Existing CRUD endpoints ----------
class OrganizationCreate(BaseModel):
    name: str
    business_type: str = None
    plan: str = "basic"

@router.get("")
async def list_organizations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    return orgs

@router.post("")
async def create_organization(org: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    new_org = Organization(name=org.name, business_type=org.business_type, plan=org.plan)
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    return new_org

@router.get("/{org_id}")
async def get_organization(org_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    return org

# ---------- New Profile & Password endpoints ----------
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    description: Optional[str] = None
    gst: Optional[str] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

@router.get("/profile")
async def get_profile(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(400, "No organization associated")
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    return org

@router.put("/profile")
async def update_profile(update: ProfileUpdate, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(400, "No organization associated")
    # Update organization fields
    stmt = update(Organization).where(Organization.id == org_id).values(
        name=update.name,
        business_type=update.business_type,
        settings={"gst": update.gst, "description": update.description}
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "updated"}

@router.post("/change-password")
async def change_password(data: ChangePassword, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password incorrect")
    new_hash = hash_password(data.new_password)
    user.password_hash = new_hash
    await db.commit()
    return {"status": "password updated"}