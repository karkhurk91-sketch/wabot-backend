import httpx
from modules.common.config import WHATSAPP_API_URL, WHATSAPP_ACCESS_TOKEN
from modules.common.logger import get_logger

logger = get_logger(__name__)

async def send_whatsapp_template(to_number: str, template_name: str, language_code: str = "en", components: list = None):
    """Send a template message (required for first contact)."""
    url = WHATSAPP_API_URL
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
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

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            logger.info(f"Template sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send template to {to_number}: {response.text}")
            return False

async def send_whatsapp_text(to_number: str, text: str):
    """Send free‑form text (allowed only after customer has messaged within 24h)."""
    url = WHATSAPP_API_URL
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            logger.info(f"Text message sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send text to {to_number}: {response.text}")
            return False