import os
from dotenv import load_dotenv

load_dotenv()

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# WhatsApp
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "default_verify_token")
WHATSAPP_API_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
WhatsApp_Business_Account_ID=os.getenv("WhatsApp_Business_Account_ID")


# AI
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/wabot_db")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# App
APP_NAME = os.getenv("APP_NAME", "WAai Backend")
QUEUE_BACKEND = os.getenv("QUEUE_BACKEND", "nano")  # 'celery' or 'nano'
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))




# EMAIL SETTINGS
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
