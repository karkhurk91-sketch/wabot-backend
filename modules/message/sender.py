import asyncio
import json
import httpx
from sqlalchemy import text
from modules.common.logger import get_logger
from modules.common.database import sync_engine
from concurrent.futures import ThreadPoolExecutor

logger = get_logger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

# ---------- Helper: synchronous DB fetch of WhatsApp config ----------
def _get_whatsapp_config_sync(org_id: str):
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT config
                FROM organization_channels
                WHERE organization_id = :org_id
                  AND channel_type = 'whatsapp'
                  AND enabled = TRUE
                LIMIT 1
            """),
            {"org_id": org_id}
        )
        row = result.fetchone()
        if not row:
            return None
        config = row[0]
        if isinstance(config, str):
            config = json.loads(config)
        return config

async def get_whatsapp_config(org_id: str):
    """Fetch WhatsApp credentials for an organization."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _get_whatsapp_config_sync, org_id)

# ---------- Message counting (optional) ----------
async def increment_message_count(org_id: str, category: str):
    """Increment marketing/utility message count."""
    if not org_id:
        return
    col = "marketing_message_count" if category.upper() == "MARKETING" else "utility_message_count"

    def _update():
        with sync_engine.connect() as conn:
            conn.execute(
                text(f"UPDATE organizations SET {col} = {col} + 1, last_count_reset = CURRENT_DATE WHERE id = :org_id"),
                {"org_id": org_id}
            )
            conn.commit()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _update)

# ---------- Send WhatsApp template (used by broadcast) ----------
async def send_whatsapp_template(
    to_number: str,
    template_name: str,
    language_code: str = "en",
    components: list = None,
    category: str = None,
    org_id: str = None
):
    """Send a template message (required for first contact)."""
    if not org_id:
        logger.error("Missing org_id – cannot send template")
        return False

    config = await get_whatsapp_config(org_id)
    if not config:
        logger.error(f"No active WhatsApp channel for org {org_id}")
        return False

    access_token = config.get("access_token")
    phone_number_id = config.get("phone_number_id")
    if not access_token or not phone_number_id:
        logger.error(f"Incomplete WhatsApp config for org {org_id}")
        return False

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code}
        }
    }
    if components:
        payload["template"]["components"] = components

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Template sent to {to_number} (org={org_id})")
                if category and org_id:
                    await increment_message_count(org_id, category)
                return True
            else:
                logger.error(f"Failed to send template: {response.text}")
                return False
    except Exception as e:
        logger.exception(f"Exception in send_whatsapp_template: {e}")
        return False

# ---------- Send WhatsApp free‑form text (only after customer message) ----------
async def send_whatsapp_text(to_number: str, text: str, org_id: str = None):
    """Send a free‑form text message (allowed only within 24h session)."""
    if not org_id:
        logger.error("Missing org_id – cannot send text")
        return False

    config = await get_whatsapp_config(org_id)
    if not config:
        logger.error(f"No active WhatsApp channel for org {org_id}")
        return False

    access_token = config.get("access_token")
    phone_number_id = config.get("phone_number_id")
    if not access_token or not phone_number_id:
        logger.error(f"Incomplete WhatsApp config for org {org_id}")
        return False

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Text message sent to {to_number} (org={org_id})")
                return True
            else:
                logger.error(f"Failed to send text: {response.text}")
                return False
    except Exception as e:
        logger.exception(f"Exception in send_whatsapp_text: {e}")
        return False