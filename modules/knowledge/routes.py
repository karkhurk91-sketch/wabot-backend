import os
import shutil
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.common.database import get_db
from modules.common.models import KnowledgeDocument
from modules.auth.jwt import get_current_user
from fastapi.responses import FileResponse
from modules.ai.rag import index_document

from typing import List

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

# Ensure upload directory exists
UPLOAD_DIR = "uploads/knowledge"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.organization_id == current_user["org_id"])
    )
    return result.scalars().all()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Generate unique filename to avoid collisions
    unique_filename = f"{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")
    
    # Create database record
    doc = KnowledgeDocument(
        id=uuid4(),
        organization_id=current_user["org_id"],
        title=title or file.filename,
        description=description,
        file_name=file.filename,
        file_url=file_path,
        file_type=file.filename.split('.')[-1] if '.' in file.filename else "",
        status="ready"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    index_document(doc.id, str(current_user["org_id"]), file_path, file_type)
    return doc

@router.put("/{doc_id}")
async def update_document(
    doc_id: str,
    title: str = Form(None),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == current_user["org_id"]
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if title is not None:
        doc.title = title
    if description is not None:
        doc.description = description
    await db.commit()
    return doc

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == current_user["org_id"]
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Delete file from disk
    if os.path.exists(doc.file_url):
        os.remove(doc.file_url)
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}

@router.get("/download/{doc_id}")
async def download_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Fetch document metadata
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == current_user["org_id"]
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not os.path.exists(doc.file_url):
        raise HTTPException(404, "File not found on server")
    
    # Return file with original filename (FastAPI sets correct Content-Disposition)
    return FileResponse(
        path=doc.file_url,
        filename=doc.file_name,   # original name including extension
        media_type="application/octet-stream"  # or detect based on extension
    )