-- Apply AFTER 001_initial.sql, using psql --single-transaction.
-- Existing PostgreSQL installations use the migration below; new
-- installations still apply 001 followed by 002 in order.

ALTER TABLE users ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL
    DEFAULT 1 CHECK (version >= 1);

INSERT INTO schema_migrations(version) VALUES ('002_user_management')
ON CONFLICT (version) DO NOTHING;
