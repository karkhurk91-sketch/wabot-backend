
-- Migration: add social media tables
CREATE TABLE IF NOT EXISTS social_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS social_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    platform VARCHAR(50) NOT NULL,
    post_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'draft',
    content TEXT,
    media_url TEXT,
    published_at TIMESTAMPTZ,
    platform_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS social_ad_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    campaign_id VARCHAR(255),
    adset_id VARCHAR(255),
    ad_id VARCHAR(255),
    lead_form_id VARCHAR(255),
    name VARCHAR(255),
    objective VARCHAR(50),
    status VARCHAR(50),
    daily_budget INTEGER,
    targeting JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
