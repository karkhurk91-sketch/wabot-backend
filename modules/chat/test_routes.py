
# modules/chat/test_routes.py (new file)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from modules.auth.jwt import get_current_super_admin
from modules.ai.agent import get_agent_for_user_compat
from modules.common.database import sync_engine
from sqlalchemy import text
from modules.common.logger import get_logger

router = APIRouter(prefix="/api/admin/ai-test", tags=["Admin AI Test"])
logger = get_logger(__name__)

class TestChatRequest(BaseModel):
    organization_id: str
    message: str

class TestChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=TestChatResponse)
async def test_ai_chat(
    req: TestChatRequest,
    _ = Depends(get_current_super_admin)
):
    # Verify organization exists
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM organizations WHERE id = :org_id"),
            {"org_id": req.organization_id}
        )
        if not result.fetchone():
            raise HTTPException(404, "Organization not found")
    
    # Use a dummy user ID (since super admin is testing)
    agent = get_agent_for_user_compat("test_user_" + req.organization_id, req.organization_id)
    reply = agent.predict(req.message)
    return TestChatResponse(reply=reply)
