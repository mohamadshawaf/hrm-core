-- HRM Core: INITIAL PostgreSQL schema for fresh installations only.
-- Does NOT migrate existing SQLite data or enable production deployment.
-- Execute only against a dedicated, empty database using a privileged DBA.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('pending_email', 'active', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(12) NOT NULL CHECK (role IN ('owner', 'hr', 'viewer')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_org_email_lower
    ON users (organization_id, lower(email));

CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    employee_code VARCHAR(30) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    job_title VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    email VARCHAR(254),
    phone VARCHAR(30),
    hire_date DATE NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (organization_id, employee_code)
);

CREATE INDEX IF NOT EXISTS idx_employees_org_name
    ON employees (organization_id, archived_at, full_name);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    actor_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(60) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id UUID NOT NULL,
    changed_fields JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_org_time
    ON audit_events (organization_id, created_at DESC);

CREATE TABLE IF NOT EXISTS email_verifications (
    token_hash CHAR(64) PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    owner_id UUID NOT NULL REFERENCES users(id),
    issued_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    consumed_at BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_verifications_org
    ON email_verifications (organization_id);

CREATE TABLE IF NOT EXISTS platform_admins (
    id UUID PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'platform_owner'
        CHECK (role = 'platform_owner'),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_admin_email_lower
    ON platform_admins (lower(email));

CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    price_halalas BIGINT NOT NULL CHECK (price_halalas >= 0),
    max_employees INTEGER NOT NULL CHECK (max_employees >= 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_subscriptions (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id),
    plan_id UUID NOT NULL REFERENCES subscription_plans(id),
    status VARCHAR(16) NOT NULL
        CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
    period_ends_at BIGINT NOT NULL CHECK (period_ends_at > 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_plan
    ON organization_subscriptions (plan_id, status);

CREATE TABLE IF NOT EXISTS platform_audit_events (
    id UUID PRIMARY KEY,
    actor_id UUID NOT NULL REFERENCES platform_admins(id),
    organization_id UUID REFERENCES organizations(id),
    action VARCHAR(60) NOT NULL,
    entity_id UUID NOT NULL,
    changed_fields JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_platform_audit_time
    ON platform_audit_events (created_at DESC);

INSERT INTO subscription_plans (id, code, name, price_halalas, max_employees)
VALUES ('00000000-0000-4000-8000-000000000001', 'starter-trial',
        'Starter Trial', 0, 25)
ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_migrations (version)
VALUES ('001_initial') ON CONFLICT (version) DO NOTHING;
