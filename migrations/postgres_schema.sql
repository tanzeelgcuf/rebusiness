-- =============================================================================
-- PostgreSQL Schema for Multi-Tenant SaaS RFQ Automation Platform
-- =============================================================================
-- Migration from SQLite to PostgreSQL
-- Features:
--   - Multi-tenant isolation via tenant_id columns
--   - JSONB columns for flexible metadata
--   - Proper indexes for query performance
--   - Row-Level Security (RLS) policies for defense in depth
--   - ENUMs for type safety
--   - Triggers for updated_at timestamps
-- =============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM Types
-- =============================================================================
CREATE TYPE subscription_tier AS ENUM ('basic', 'pro', 'enterprise');
CREATE TYPE tenant_status AS ENUM ('active', 'trial', 'suspended', 'cancelled');
CREATE TYPE user_role AS ENUM ('admin', 'procurement_manager', 'viewer');
CREATE TYPE run_status AS ENUM ('queued', 'running', 'completed', 'failed', 'completed_with_errors', 'cancelled');
CREATE TYPE log_status AS ENUM ('pending', 'running', 'success', 'retry', 'failed', 'skipped');
CREATE TYPE sam_gov_status AS ENUM ('disconnected', 'connected', 'syncing', 'error', 'rate_limited');
CREATE TYPE submission_method AS ENUM ('email', 'thomasnet', 'both');

-- =============================================================================
-- Tenants
-- =============================================================================
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT uuid_generate_v4() UNIQUE,
    slug VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    subscription_tier subscription_tier NOT NULL DEFAULT 'basic',
    status tenant_status NOT NULL DEFAULT 'active',
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    api_quota_used INTEGER NOT NULL DEFAULT 0,
    api_quota_limit INTEGER NOT NULL DEFAULT 1000,
    stripe_customer_id VARCHAR(128) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tier ON tenants(subscription_tier);
CREATE INDEX idx_tenants_created_at ON tenants(created_at DESC);

COMMENT ON TABLE tenants IS 'Multi-tenant organizations on the SaaS platform';

-- =============================================================================
-- Users
-- =============================================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT uuid_generate_v4() UNIQUE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role user_role NOT NULL DEFAULT 'procurement_manager',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login TIMESTAMP WITH TIME ZONE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE users IS 'Per-tenant users with role-based access control';

-- =============================================================================
-- SAM.gov Credentials (encrypted at rest)
-- =============================================================================
CREATE TABLE sam_gov_credentials (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    api_key_encrypted TEXT NOT NULL,
    entity_id VARCHAR(128) NOT NULL,
    api_key_last4 VARCHAR(4),
    connection_status sam_gov_status NOT NULL DEFAULT 'disconnected',
    last_test_at TIMESTAMP WITH TIME ZONE,
    last_test_success BOOLEAN,
    last_test_error TEXT,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_count INTEGER NOT NULL DEFAULT 0,
    rate_limit_remaining INTEGER,
    rate_limit_reset_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sam_gov_status ON sam_gov_credentials(connection_status);
CREATE INDEX idx_sam_gov_last_sync ON sam_gov_credentials(last_sync_at DESC);

COMMENT ON TABLE sam_gov_credentials IS 'Tenant-specific SAM.gov API credentials (encrypted at rest)';

-- =============================================================================
-- SAM.gov Sync History
-- =============================================================================
CREATE TABLE sam_gov_sync_history (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    credentials_id INTEGER NOT NULL REFERENCES sam_gov_credentials(id) ON DELETE CASCADE,
    sync_started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sync_completed_at TIMESTAMP WITH TIME ZONE,
    status log_status NOT NULL DEFAULT 'running',
    solicitations_fetched INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    duration_ms INTEGER
);

CREATE INDEX idx_sam_gov_sync_tenant ON sam_gov_sync_history(tenant_id, sync_started_at DESC);

-- =============================================================================
-- Automation Runs
-- =============================================================================
CREATE TABLE automation_runs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    celery_task_id VARCHAR(128) UNIQUE,
    status run_status NOT NULL DEFAULT 'queued',
    progress_percent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    current_step INTEGER NOT NULL DEFAULT 0,
    results JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_automation_runs_tenant_created ON automation_runs(tenant_id, created_at DESC);
CREATE INDEX idx_automation_runs_status ON automation_runs(status) WHERE status IN ('queued', 'running');
CREATE INDEX idx_automation_runs_user ON automation_runs(user_id, created_at DESC);
CREATE INDEX idx_automation_runs_celery ON automation_runs(celery_task_id) WHERE celery_task_id IS NOT NULL;

COMMENT ON TABLE automation_runs IS 'Top-level automation workflow execution records';

-- =============================================================================
-- Agent Loop Logs
-- =============================================================================
CREATE TABLE agent_loop_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    automation_run_id INTEGER NOT NULL REFERENCES automation_runs(id) ON DELETE CASCADE,
    agent_name VARCHAR(64) NOT NULL,
    step_number INTEGER NOT NULL CHECK (step_number BETWEEN 1 AND 10),
    status log_status NOT NULL DEFAULT 'pending',
    attempt_number INTEGER NOT NULL DEFAULT 1,
    retry_count_max INTEGER NOT NULL DEFAULT 2,
    error_message TEXT,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_loop_logs_run ON agent_loop_logs(automation_run_id, step_number);
CREATE INDEX idx_agent_loop_logs_tenant ON agent_loop_logs(tenant_id, created_at DESC);
CREATE INDEX idx_agent_loop_logs_status ON agent_loop_logs(status) WHERE status IN ('pending', 'running', 'retry');

COMMENT ON TABLE agent_loop_logs IS 'Per-step agent execution logs with retry tracking';

-- =============================================================================
-- Audit Logs
-- =============================================================================
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(64),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_tenant_created ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

COMMENT ON TABLE audit_logs IS 'Compliance audit trail (immutable)';

-- =============================================================================
-- Solicitations (from SAM.gov)
-- =============================================================================
CREATE TABLE solicitations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    automation_run_id INTEGER REFERENCES automation_runs(id) ON DELETE SET NULL,
    solicitation_id VARCHAR(128) NOT NULL,
    title TEXT NOT NULL,
    agency VARCHAR(255),
    office VARCHAR(255),
    posted_date DATE,
    response_deadline TIMESTAMP WITH TIME ZONE,
    naics_code VARCHAR(16),
    classification_code VARCHAR(16),
    set_aside VARCHAR(128),
    description TEXT,
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, solicitation_id)
);

CREATE INDEX idx_solicitations_tenant ON solicitations(tenant_id, created_at DESC);
CREATE INDEX idx_solicitations_deadline ON solicitations(response_deadline) WHERE response_deadline IS NOT NULL;
CREATE INDEX idx_solicitations_naics ON solicitations(naics_code);

-- =============================================================================
-- RFQ Outputs
-- =============================================================================
CREATE TABLE rfq_outputs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    automation_run_id INTEGER REFERENCES automation_runs(id) ON DELETE SET NULL,
    solicitation_id INTEGER REFERENCES solicitations(id) ON DELETE SET NULL,
    contract_id VARCHAR(128) NOT NULL,
    rfq_type VARCHAR(32) NOT NULL DEFAULT 'PRODUCT',
    format VARCHAR(16) NOT NULL DEFAULT 'markdown',
    content TEXT NOT NULL,
    content_length INTEGER NOT NULL DEFAULT 0,
    products_extracted INTEGER NOT NULL DEFAULT 0,
    generated_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sent_to_vendor BOOLEAN NOT NULL DEFAULT FALSE,
    sent_date TIMESTAMP WITH TIME ZONE,
    vendor_email_recipient TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, contract_id)
);

CREATE INDEX idx_rfq_outputs_tenant_created ON rfq_outputs(tenant_id, created_at DESC);
CREATE INDEX idx_rfq_outputs_sent ON rfq_outputs(sent_to_vendor, sent_date) WHERE sent_to_vendor = TRUE;
CREATE INDEX idx_rfq_outputs_solicitation ON rfq_outputs(solicitation_id);

-- =============================================================================
-- Vendors
-- =============================================================================
CREATE TABLE vendors (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    automation_run_id INTEGER REFERENCES automation_runs(id) ON DELETE SET NULL,
    contract_id VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    website VARCHAR(512),
    email VARCHAR(255),
    phone VARCHAR(64),
    location VARCHAR(255),
    confidence_score INTEGER CHECK (confidence_score BETWEEN 0 AND 100),
    email_status VARCHAR(32) NOT NULL DEFAULT 'Pending',
    source VARCHAR(64) NOT NULL DEFAULT 'thomasnet',
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_contacted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vendors_tenant_created ON vendors(tenant_id, created_at DESC);
CREATE INDEX idx_vendors_email_status ON vendors(email_status);
CREATE INDEX idx_vendors_contract ON vendors(contract_id);
CREATE INDEX idx_vendors_confidence ON vendors(confidence_score DESC);

-- =============================================================================
-- Triggers: updated_at auto-update
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sam_gov_credentials_updated_at BEFORE UPDATE ON sam_gov_credentials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_automation_runs_updated_at BEFORE UPDATE ON automation_runs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vendors_updated_at BEFORE UPDATE ON vendors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Row-Level Security (Defense in Depth)
-- =============================================================================
-- Even though queries are filtered by tenant_id in application code,
-- enable RLS as an additional safety net.
-- =============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE automation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_loop_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE solicitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE rfq_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE sam_gov_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE sam_gov_sync_history ENABLE ROW LEVEL SECURITY;

-- Note: RLS policies are typically set up per-application-user.
-- For service account access, use SET LOCAL app.current_tenant_id = X
-- and create policies like:
--
-- CREATE POLICY tenant_isolation_users ON users
--   USING (tenant_id = current_setting('app.current_tenant_id')::integer);
--
-- For the application, the service account runs as a privileged role
-- and application code enforces tenant filtering.

-- =============================================================================
-- Functions for multi-tenant queries
-- =============================================================================

-- Get tenant usage stats
CREATE OR REPLACE FUNCTION get_tenant_stats(p_tenant_id INTEGER)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'automations', (
            SELECT jsonb_build_object(
                'total', COUNT(*),
                'completed', COUNT(*) FILTER (WHERE status = 'completed'),
                'failed', COUNT(*) FILTER (WHERE status = 'failed'),
                'running', COUNT(*) FILTER (WHERE status = 'running')
            )
            FROM automation_runs WHERE tenant_id = p_tenant_id
        ),
        'rfqs', (
            SELECT jsonb_build_object(
                'total', COUNT(*),
                'sent', COUNT(*) FILTER (WHERE sent_to_vendor = TRUE)
            )
            FROM rfq_outputs WHERE tenant_id = p_tenant_id
        ),
        'vendors', (
            SELECT jsonb_build_object(
                'total', COUNT(*),
                'with_email', COUNT(*) FILTER (WHERE email IS NOT NULL)
            )
            FROM vendors WHERE tenant_id = p_tenant_id
        ),
        'solicitations', (
            SELECT jsonb_build_object('total', COUNT(*))
            FROM solicitations WHERE tenant_id = p_tenant_id
        )
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Views for common queries
-- =============================================================================

CREATE OR REPLACE VIEW v_automation_summary AS
SELECT
    ar.id,
    ar.tenant_id,
    ar.user_id,
    ar.status,
    ar.progress_percent,
    ar.results,
    ar.start_time,
    ar.end_time,
    ar.duration_seconds,
    ar.created_at,
    u.email AS user_email,
    u.full_name AS user_name,
    t.name AS tenant_name,
    t.subscription_tier
FROM automation_runs ar
JOIN users u ON ar.user_id = u.id
JOIN tenants t ON ar.tenant_id = t.id;

CREATE OR REPLACE VIEW v_recent_agent_logs AS
SELECT
    al.id,
    al.tenant_id,
    al.automation_run_id,
    al.agent_name,
    al.step_number,
    al.status,
    al.attempt_number,
    al.error_message,
    al.duration_ms,
    al.created_at
FROM agent_loop_logs al
WHERE al.created_at > NOW() - INTERVAL '7 days';

-- =============================================================================
-- Seed: Default tenant (for development)
-- =============================================================================
-- INSERT INTO tenants (slug, name, subscription_tier, status)
-- VALUES ('demo', 'Demo Company', 'pro', 'active');

-- =============================================================================
-- Maintenance
-- =============================================================================

-- Vacuum analyze for query planner
VACUUM ANALYZE;

-- Migration complete
SELECT 'PostgreSQL schema migration complete' AS status;
