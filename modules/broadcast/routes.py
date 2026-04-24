from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from modules.common.database import get_db
from modules.common.models import BroadcastTemplate, BroadcastHistory, Customer, Organization
from modules.auth.jwt import get_current_user
from modules.common.config import WHATSAPP_ACCESS_TOKEN
from modules.message.sender import send_whatsapp_template
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
import httpx
import asyncio

router = APIRouter(prefix="/api/broadcast", tags=["Broadcast"])

# ---------- Pydantic models ----------
class TemplateCreate(BaseModel):
    name: str
    content: str
    media_url: Optional[str] = None
    meta_template_name: Optional[str] = None
    language_code: Optional[str] = "en_US"
    category: str = "MARKETING"   # or "UTILITY"

class BroadcastSend(BaseModel):
    template_id: UUID
    recipient_ids: List[UUID]

class SendMetaBroadcast(BaseModel):
    template_name: str
    language_code: str = "en_US"
    recipient_phone_numbers: List[str]

# ---------- Helper: Get org credentials (used for Meta template fetch) ----------
async def get_org_credentials(org_id: str, db: AsyncSession):
    result = await db.execute(select(Organization).where(Organization.id == UUID(org_id)))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    return org

# ---------- Local templates (for future use, not used in direct broadcast) ----------
@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    result = await db.execute(
        select(BroadcastTemplate).where(BroadcastTemplate.organization_id == current_user["org_id"])
        .order_by(BroadcastTemplate.created_at.desc())
    )
    return result.scalars().all()

@router.post("/templates")
async def create_template(data: TemplateCreate, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    template = BroadcastTemplate(
        organization_id=current_user["org_id"],
        name=data.name,
        content=data.content,
        media_url=data.media_url,
        status="pending",
        meta_template_name=data.meta_template_name,
        language_code=data.language_code,
        category=data.category 
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template

@router.post("/templates/{template_id}/submit")
async def submit_template(template_id: UUID, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    stmt = update(BroadcastTemplate).where(
        BroadcastTemplate.id == template_id,
        BroadcastTemplate.organization_id == current_user["org_id"]
    ).values(status="approved")
    await db.execute(stmt)
    await db.commit()
    return {"status": "approved"}

# ---------- NEW: Send broadcast using approved Meta template (organization‑specific) ----------
@router.post("/send-meta")
async def send_meta_broadcast(
    data: SendMetaBroadcast,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    if not data.recipient_phone_numbers:
        raise HTTPException(400, "No recipients provided")
    if not data.template_name:
        raise HTTPException(400, "Template name is required")

    background_tasks.add_task(
        send_bulk_template_messages,
        recipients=data.recipient_phone_numbers,
        template_name=data.template_name,
        language_code=data.language_code,
        org_id=current_user["org_id"],
        category=template.category
    )

    return {
        "status": "queued",
        "recipient_count": len(data.recipient_phone_numbers),
        "template": data.template_name
    }

# ---------- Background worker for sending template messages ----------
async def send_bulk_template_messages(recipients: list, template_name: str, language_code: str, org_id: str, category: str):
    for phone in recipients:
        success = await send_whatsapp_template(
            to_number=phone,
            template_name=template_name,
            language_code=language_code,
            category=category
        )
        # org_id not used here
        await asyncio.sleep(0.5)

# ---------- Fetch approved templates from Meta (using organization's credentials) ----------
@router.get("/meta-templates")
async def fetch_meta_templates(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org = await get_org_credentials(current_user["org_id"], db)
    access_token = WHATSAPP_ACCESS_TOKEN
    waba_id = org.whatsapp_business_account_id

    if not waba_id:
        # Fallback: fetch WABA ID from Meta
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://graph.facebook.com/v21.0/me/whatsapp_business_accounts",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                waba_id = data["data"][0]["id"]
                # Store it back for future use
                org.whatsapp_business_account_id = waba_id
                await db.commit()
            else:
                raise HTTPException(400, "No WhatsApp Business Account found")

    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    params = {}
    if category:
        params["category"] = category.upper()
    if status:
        params["status"] = status.upper()

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    templates = []
    for t in data.get("data", []):
        templates.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "status": t.get("status"),
            "category": t.get("category"),
            "language": t.get("language"),
            "components": t.get("components", []),
        })
    return templates