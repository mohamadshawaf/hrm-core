"""Development SQLite adapter. Replace with PostgreSQL before deployment."""

import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from collections.abc import Iterator

from .postgres_adapter import is_postgres_dsn, postgres_initialize, postgres_session, POSTGRES_UNIQUE_ERROR


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
STARTER_PLAN_ID = '00000000-0000-4000-8000-000000000001'
TRIAL_DURATION_SECONDS = 14 * 24 * 60 * 60
UNIQUE_ERRORS = (sqlite3.IntegrityError, POSTGRES_UNIQUE_ERROR)


def connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


@contextmanager
def session(db_path: str) -> Iterator:
    if is_postgres_dsn(db_path):
        with postgres_session(db_path) as connection:
            yield connection
        return
    connection = connect(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(db_path: str) -> None:
    if is_postgres_dsn(db_path):
        postgres_initialize(db_path, STARTER_PLAN_ID, TRIAL_DURATION_SECONDS)
        return
    if '://' in db_path:
        raise RuntimeError('Unsupported database scheme; use PostgreSQL URL or local SQLite path')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = connect(db_path)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Backward-compatible *development* upgrade for milestone-1 SQLite
        # databases. Production will use explicit PostgreSQL migrations.
        org_fields = {row['name'] for row in connection.execute('PRAGMA table_info(organizations)')}
        if 'status' not in org_fields:
            connection.execute(
                "ALTER TABLE organizations ADD COLUMN status TEXT NOT NULL "
                "DEFAULT 'active' CHECK (status IN ('pending_email', 'active', 'suspended'))"
            )
        user_fields = {row['name'] for row in connection.execute('PRAGMA table_info(users)')}
        if 'version' not in user_fields:
            connection.execute(
                'ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 1 '
                'CHECK (version >= 1)'
            )
        # Idempotent local-development seed and backward-compatible backfill.
        # Changing the seed never alters an existing plan or subscription.
        connection.execute(
            "INSERT OR IGNORE INTO subscription_plans "
            "(id,code,name,price_halalas,max_employees) VALUES (?,?,?,?,?)",
            (STARTER_PLAN_ID, 'starter-trial', 'Starter Trial', 0, 25),
        )
        connection.execute(
            "INSERT OR IGNORE INTO organization_subscriptions "
            "(organization_id,plan_id,status,period_ends_at) "
            "SELECT id, ?, 'trialing', ? FROM organizations",
            (STARTER_PLAN_ID, int(time.time()) + TRIAL_DURATION_SECONDS),
        )
        connection.commit()
    finally:
        connection.close()
