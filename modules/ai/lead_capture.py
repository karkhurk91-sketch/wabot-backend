# modules/ai/lead_capture.py
import httpx
from modules.common.config import API_BASE_URL
from modules.common.logger import get_logger

logger = get_logger(__name__)

async def create_lead(org_id: str, customer_phone: str, interest: str, customer_name: str = ""):
    """Create a lead via internal API call (or directly insert into DB)."""
    # Option 1: Direct DB insert (simpler)
    from modules.common.database import AsyncSessionLocal
    from modules.common.models import Lead
    import uuid
    async with AsyncSessionLocal() as session:
        lead = Lead(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            customer_phone=customer_phone,
            customer_name=customer_name,
            interest=interest,
            status="new"
        )
        session.add(lead)
        await session.commit()
        logger.info(f"Lead created for {customer_phone}")