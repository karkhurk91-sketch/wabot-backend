from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.common.database import get_db
from modules.common.models import User, Organization
from modules.auth.jwt import hash_password, verify_password, create_access_token
from modules.common.config import SECRET_KEY, ALGORITHM, FRONTEND_URL
from modules.common.email import send_email
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import secrets
from datetime import timedelta
from jose import jwt



router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ---------- Pydantic models ----------
class SignupRequest(BaseModel):
    name: str
    business_type: Optional[str] = None
    gst: Optional[str] = None
    description: Optional[str] = None
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# ---------- Public signup with email verification ----------
@router.post("/signup")
async def public_signup(
    req: SignupRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Check if email already used
    result = await db.execute(select(User).where(User.email == req.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(400, "Email already registered")

    # Create organization with status 'pending'
    new_org = Organization(
        name=req.name,
        business_type=req.business_type,
        status="pending",
        settings={"gst": req.gst, "description": req.description}
    )
    db.add(new_org)
    await db.flush()

    # Create admin user for this organization
    hashed = hash_password(req.password)
    verification_token = secrets.token_urlsafe(32)
    new_user = User(
        email=req.email,
        password_hash=hashed,
        full_name=req.name,
        role="org_admin",
        organization_id=new_org.id,
        is_active=True,
        email_verified=False,
        verification_token=verification_token
    )
    db.add(new_user)
    await db.commit()

    # Send verification email in background
    verification_link = f"{FRONTEND_URL}/verify-email?token={verification_token}"
    email_body = f"""
    <h2>Welcome to WAAI!</h2>
    <p>Please verify your email by clicking the link below:</p>
    <a href="{verification_link}">Verify Email</a>
    <p>This link will expire in 24 hours.</p>
    """
    background_tasks.add_task(send_email, req.email, "Verify your email", email_body)

    return {"message": "Registration successful. Please check your email to verify your account."}

@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(400, "Invalid or expired token")
    user.email_verified = True
    user.verification_token = None
    await db.commit()
    return {"message": "Email verified. You can now log in."}

# ---------- Login (checks email verification) ----------
@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(401, "Account disabled")
    if not user.email_verified:
        raise HTTPException(401, "Email not verified. Please check your inbox.")
    # Check organization status if user is org_admin
    if user.role == "org_admin":
        org_result = await db.execute(select(Organization).where(Organization.id == user.organization_id))
        org = org_result.scalar_one_or_none()
        if not org or org.status != "active":
            raise HTTPException(401, "Organization not approved or suspended")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    # Update last_login
    user.last_login = func.now()
    await db.commit()
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "org_id": str(user.organization_id) if user.organization_id else None
    }
    access_token = create_access_token(token_data)
    return {"access_token": access_token, "token_type": "bearer"}

# ---------- Forgot password (sends reset link) ----------
@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        # Don't reveal if email exists
        return {"message": "If an account exists, a reset link has been sent."}
    # Create a short-lived JWT token for password reset
    reset_token = create_access_token(
        data={"sub": str(user.id), "purpose": "reset"},
        expires_delta=timedelta(minutes=30)
    )
    reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    email_body = f"""
    <h2>Password Reset Request</h2>
    <p>Click the link below to reset your password. This link expires in 30 minutes.</p>
    <a href="{reset_link}">Reset Password</a>
    """
    background_tasks.add_task(send_email, user.email, "Reset your password", email_body)
    return {"message": "If an account exists, a reset link has been sent."}

# ---------- Reset password ----------
@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "reset":
            raise HTTPException(400, "Invalid token")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(400, "Invalid token")
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(400, "User not found")
        new_hash = hash_password(req.new_password)
        user.password_hash = new_hash
        await db.commit()
        return {"message": "Password updated. You can now log in."}
    except Exception:
        raise HTTPException(400, "Invalid or expired token")

# ========== TEMPORARY: Create super admin (remove after first use) ==========
@router.post("/create-super-admin")
async def create_super_admin(
    secret: str,
    db: AsyncSession = Depends(get_db)
):
    # Protect the endpoint with a secret (use a random string)
    if secret != "myWhatsApp2026":
        raise HTTPException(403, "Invalid secret")
    
    # Check if already exists
    result = await db.execute(select(User).where(User.email == "admin@sahai.ai"))
    if result.scalar_one_or_none():
        return {"message": "Admin already exists"}
    
    # Create super admin
    hashed = hash_password("admin123")  # uses your existing hash_password function
    new_user = User(
        email="admin@sahai.ai",
        password_hash=hashed,
        full_name="Super Admin",
        role="super_admin",
        is_active=True,
        email_verified=True
    )
    db.add(new_user)
    await db.commit()
    return {"message": "Super admin created. Email: admin@sahai.ai, Password: admin123"}


@app.post("/admin/setup", status_code=201)
async def setup_super_admin(db: AsyncSession = Depends(get_db)):
    # Check if admin already exists
    existing_user = await db.execute(select(User).where(User.email == "admin@sahai.ai"))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Super admin already exists")
    # Create a new super admin
    hashed_password = hash_password("admin123")
    new_admin = User(
        email="admin@sahai.ai",
        password_hash=hashed_password,
        full_name="Super Admin",
        role="super_admin",
        is_active=True,
        email_verified=True
    )
    db.add(new_admin)
    await db.commit()
    return {"message": "Super admin created successfully"}