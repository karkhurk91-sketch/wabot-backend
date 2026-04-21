from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from modules.common.database import get_db
from modules.common.models import Customer
from modules.auth.jwt import get_current_user
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from datetime import datetime

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
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    query = select(Customer).where(Customer.organization_id == org_id, Customer.deleted_at.is_(None))
    if search:
        query = query.where(Customer.phone_number.contains(search) | Customer.name.contains(search))
    result = await db.execute(query.order_by(Customer.created_at.desc()))
    return result.scalars().all()

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
