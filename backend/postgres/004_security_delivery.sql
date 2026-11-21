-- Run only after PostgreSQL migrations 001 through 003.

CREATE TABLE IF NOT EXISTS rate_limit_hits (
    bucket_key CHAR(64) NOT NULL,
    window_start BIGINT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    expires_at BIGINT NOT NULL,
    PRIMARY KEY (bucket_key, window_start)
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_expiry ON rate_limit_hits(expires_at);

CREATE TABLE IF NOT EXISTS mail_outbox (
    id UUID PRIMARY KEY,
    kind VARCHAR(20) NOT NULL CHECK(kind IN ('verification','invitation','reset')),
    recipient_email VARCHAR(254) NOT NULL,
    nonce BYTEA,
    ciphertext BYTEA,
    status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','processing','sent','dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at BIGINT NOT NULL,
    lease_until BIGINT,
    created_at BIGINT NOT NULL,
    sent_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_mail_outbox_work
    ON mail_outbox(status,next_attempt_at,lease_until);

INSERT INTO schema_migrations(version) VALUES ('004_security_delivery')
ON CONFLICT (version) DO NOTHING;
