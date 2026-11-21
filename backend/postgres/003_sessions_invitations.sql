-- Run AFTER 001_initial.sql and 002_user_management.sql.

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    refresh_token_hash CHAR(64) NOT NULL UNIQUE,
    device_label VARCHAR(60) NOT NULL,
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    revoked_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user
    ON user_sessions (user_id, revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS consumed_refresh_tokens (
    token_hash CHAR(64) PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES user_sessions(id),
    consumed_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_invitations (
    token_hash CHAR(64) PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(254) NOT NULL,
    role VARCHAR(12) NOT NULL CHECK (role IN ('hr','viewer')),
    invited_by UUID NOT NULL REFERENCES users(id),
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    accepted_at BIGINT,
    revoked_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_user_invitations_org_email
    ON user_invitations (organization_id, lower(email), created_at DESC);

CREATE TABLE IF NOT EXISTS password_resets (
    token_hash CHAR(64) PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    consumed_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_password_resets_user
    ON password_resets (user_id, created_at DESC);

INSERT INTO schema_migrations(version) VALUES ('003_sessions_invitations')
ON CONFLICT (version) DO NOTHING;
