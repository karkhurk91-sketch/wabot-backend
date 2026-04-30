from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.message.webhook import router as webhook_router
from modules.auth.routes import router as auth_router
from modules.organizations.routes import router as org_router
from modules.admin.routes import router as admin_router
from modules.leads.routes import router as leads_router
from modules.broadcast.routes import router as broadcast_router
from modules.ai_config.routes import router as ai_config_router
from modules.conversations.routes import router as conv_router
from modules.customers.routes import router as customers_router   # <-- ADD THIS
from modules.knowledge.routes import router as knowledge_router   # if you have it
from modules.analytics.routes import router as analytics_router   # if you have it
from modules.common.config import APP_NAME, QUEUE_BACKEND
from modules.common.database import engine, Base
from modules.common.logger import get_logger
from modules.chat.routes import router as chat_router
from modules.bookings.routes import router as bookings_router
from modules.organizations.routes import router as organizations_router
from modules.admin.prompts import router as admin_prompts_router
from modules.chat.test_routes import router as admin_ai_test_router
from modules.blog.routes import router as blog_router
from modules.messages.router import router as messages_router
from modules.webhooks.router import router as webhooks_router
from sqlalchemy import text


logger = get_logger(__name__)

app = FastAPI(title=APP_NAME)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "https://wabot-backend-geky.onrender.com", "https://wabot-dashboard-one.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(org_router)
app.include_router(admin_router)
app.include_router(leads_router)
app.include_router(broadcast_router)
app.include_router(ai_config_router)
app.include_router(conv_router)
app.include_router(customers_router)   # <-- ADD THIS
app.include_router(knowledge_router)  # uncomment if exists
app.include_router(analytics_router)  # uncomment if exists
app.include_router(chat_router)
app.include_router(bookings_router)
app.include_router(organizations_router)
app.include_router(admin_prompts_router)
app.include_router(admin_ai_test_router)
app.include_router(blog_router)
app.include_router(messages_router)
app.include_router(webhooks_router)

#@app.on_event("startup")
#async def startup():
#    async with engine.begin() as conn:
#        await conn.run_sync(Base.metadata.create_all)
#    logger.info("Database tables initialized")
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Step 1: Create tables if not exist
        await conn.run_sync(Base.metadata.create_all)

        # Step 2: Add missing column safely
        await conn.execute(text("""
            ALTER TABLE customers 
            ADD COLUMN IF NOT EXISTS fb_psid VARCHAR(255)
        """))

    logger.info("Database initialized + migration applied")

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()
    logger.info("Database connection closed")

@app.get("/")
def root():
    return {"message": f"{APP_NAME} is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
