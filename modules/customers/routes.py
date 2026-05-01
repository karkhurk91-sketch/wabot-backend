from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from modules.common.database import get_db
from modules.common.models import Customer
from modules.auth.jwt import get_current_user
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import pandas as pd

router = APIRouter(prefix="/api/customers", tags=["Customers"])

class CustomerCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
async def list_customers(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user["org_id"]

    query = select(Customer).where(
        Customer.organization_id == org_id,
        Customer.deleted_at.is_(None)
    )

    if search:
        query = query.where(
            Customer.phone_number.contains(search) |
            Customer.name.contains(search)
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    result = await db.execute(
        query.order_by(Customer.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )

    customers = result.scalars().all()

    def mask_email(email):
        if not email: return None
        return email[:2] + "****@" + email.split("@")[-1]

    def mask_phone(phone):
        return phone[:3] + "****" + phone[-2:]

    return {
        "data": [
            {
                **c.__dict__,
                "email": mask_email(c.email),
                "phone_number": mask_phone(c.phone_number)
            } for c in customers
        ],
        "total": total,
        "page": page
    }

@router.post("")
async def create_customer(
    cust: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    new_cust = Customer(
        organization_id=current_user["org_id"],
        phone_number=cust.phone_number,
        name=cust.name,
        email=cust.email,
        notes=cust.notes
    )
    db.add(new_cust)
    await db.commit()
    await db.refresh(new_cust)
    return new_cust

@router.put("/{customer_id}")
async def update_customer(
    customer_id: UUID,
    update_data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    stmt = update(Customer).where(
        Customer.id == customer_id,
        Customer.organization_id == current_user["org_id"],
        Customer.deleted_at.is_(None)
    ).values(**update_data.dict(exclude_unset=True))
    await db.execute(stmt)
    await db.commit()
    return {"status": "updated"}

@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    stmt = update(Customer).where(
        Customer.id == customer_id,
        Customer.organization_id == current_user["org_id"]
    ).values(deleted_at=datetime.utcnow())
    await db.execute(stmt)
    await db.commit()
    return {"status": "deleted"}

@router.put("/{customer_id}/status")
async def toggle_customer_status(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = update(Customer).where(Customer.id == customer_id).values(
        is_active=~Customer.is_active
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "updated"}

@router.post("/upload")
async def upload_customers(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    df = pd.read_csv(file.file) if file.filename.endswith(".csv") else pd.read_excel(file.file)

    customers = []

    for _, row in df.iterrows():
        customers.append(Customer(
            organization_id=current_user["org_id"],
            phone_number=str(row.get("phone")),
            name=row.get("name"),
            email=row.get("email"),
            country_code=row.get("country_code", "+91"),
            address=row.get("address"),
            pincode=row.get("pincode"),
            profession=row.get("profession"),
        ))

    db.add_all(customers)
    await db.commit()

    return {"message": f"{len(customers)} customers uploaded"}
