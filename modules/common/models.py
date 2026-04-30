from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, Float, ForeignKey, Index, Date, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from modules.common.database import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    business_type = Column(String(100))
    whatsapp_phone_number = Column(String(100), unique=True)
    status = Column(String(20), default="pending")  # pending, active, suspended
    plan = Column(String(50), default="basic")
    settings = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), nullable=False)  # super_admin, org_admin
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    phone_number = Column(String(20), nullable=False)
    name = Column(String(255))
    email = Column(String(255))
    fb_psid = Column(String(255), nullable=True)
    instagram_id = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(255), nullable=True)
    notes = Column(Text)
    deleted_at = Column(DateTime(timezone=True))  # soft delete
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (Index("ix_customers_org_phone", organization_id, phone_number, unique=True),)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    customer_phone_number = Column(String(20), nullable=False)
    customer_name = Column(String(255))
    status = Column(String(20), default="open") 
    lead_score = Column(Integer, default=0)
    service = Column(String(100), nullable=True)
    tags = Column(ARRAY(String))
    reply_mode   = Column(String(255))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    campaign_id = Column(UUID(as_uuid=True), nullable=True)
    closed_at = Column(DateTime(timezone=True))

class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    direction = Column(String(10), nullable=False)
    message_type = Column(String(20), default="text")
    content = Column(Text, nullable=False)
    media_url = Column(Text) 
    is_ai_generated = Column(Boolean, default=True)
    human_agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="sent") 
    whatsapp_message_id = Column(String(255))


class Lead(Base):
    __tablename__ = "leads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(255))
    email = Column(String(255))
    interest = Column(String(255))
    budget_range = Column(String(50))
    status = Column(String(20), default="new")
    notes = Column(Text)
    service = Column(String(100), nullable=True)
    lead_score = Column(Integer, default=0)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AIConfig(Base):
    __tablename__ = "ai_configurations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)  # null = global default
    system_prompt = Column(Text, default="You are a helpful sales assistant...")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=500)
    model_name = Column(String(50), default="gemini-1.5-flash")
    enable_lead_capture = Column(Boolean, default=True)
    enable_auto_escalation = Column(Boolean, default=True)
    escalation_keywords = Column(ARRAY(String))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class BroadcastTemplate(Base):
    __tablename__ = "broadcast_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    media_url = Column(Text)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    meta_template_id = Column(String(100))
    meta_template_name = Column(String(100), nullable=True)
    language_code = Column(String(10), default="en_US")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class BroadcastHistory(Base):
    __tablename__ = "broadcast_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("broadcast_templates.id"))
    recipient_count = Column(Integer, default=0)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    title = Column(String(255))               # <-- NEW
    description = Column(Text)                # <-- NEW
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(String(50))
    status = Column(String(20), default="processing")
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(255))
    service = Column(String(100))
    booking_date = Column(Date)
    booking_time = Column(Time)
    status = Column(String(20), default="confirmed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class OrganizationPrompt(Base):
    __tablename__ = "organization_prompts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    prompt_text = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# ========== BLOG MODEL ==========
class Blog(Base):
    __tablename__ = "blogs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    description = Column(String(500))
    content = Column(Text, nullable=False)
    image_url = Column(String(500))
    published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class OrganizationChannel(Base):
    __tablename__ = "organization_channels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    channel_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=False)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (UniqueConstraint('organization_id', 'channel_type'),)

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(String(255))
    product_name = Column(String(255))
    price = Column(String(50))
    location = Column(String(100))
    description = Column(Text)
    whatsapp_link = Column(Text)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CampaignCreative(Base):
    __tablename__ = "campaign_creatives"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"))
    type = Column(String(20))
    content = Column(Text)
    is_selected = Column(Boolean, default=False)
    media_url = Column(Text, nullable=True)   # <-- ADD THIS LINE
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class CampaignMeta(Base):
    __tablename__ = "campaign_meta"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"))
    audience_suggestion = Column(Text)
    budget_suggestion = Column(String(50))
    platform_suggestion = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ========== SOCIAL MEDIA MODELS (for multi‑platform automation) ==========
class SocialAccount(Base):
    __tablename__ = "social_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    platform = Column(String(50), nullable=False)          # 'facebook', 'instagram', 'linkedin'
    account_id = Column(String(255), nullable=False)      # Facebook Page ID, etc.
    access_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default={})                   # e.g., {"ad_account_id": "123"}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SocialPost(Base):
    __tablename__ = "social_posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"))
    platform = Column(String(50), nullable=False)
    post_id = Column(String(255))
    status = Column(String(50), default="draft")          # 'draft', 'published', 'failed'
    content = Column(Text)
    media_url = Column(Text)
    published_at = Column(DateTime(timezone=True))
    platform_response = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SocialAdCampaign(Base):
    __tablename__ = "social_ad_campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    platform = Column(String(50), nullable=False)
    campaign_id = Column(String(255))                     # platform's campaign ID
    adset_id = Column(String(255))
    ad_id = Column(String(255))
    lead_form_id = Column(String(255))
    name = Column(String(255))
    objective = Column(String(50))                        # e.g., OUTCOME_LEADS
    status = Column(String(50))
    daily_budget = Column(Integer)                        # in smallest currency unit (e.g., paise)
    targeting = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ========== Tags & Notes for Conversations ==========
class Tag(Base):
    __tablename__ = "tags"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#4F46E5")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationTag(Base):
    __tablename__ = "conversation_tags"
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class ConversationNote(Base):
    __tablename__ = "conversation_notes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
