"""Psycopg 3 execution adapter for the existing parameterized repositories.

The repository query set uses SQLite-style positional placeholders; this
adapter converts only known internal SQL from '?' to Psycopg '%s' and maps
SQLite instr(string, substring) to PostgreSQL strpos(string, substring).
It must never accept untrusted SQL text. PostgreSQL still requires an external
migration step, real integration tests, backup drills and production hardening.
"""

from contextlib import contextmanager
from datetime import date, datetime
import json
from typing import Any
import uuid


try:
    import psycopg
    from psycopg.rows import dict_row
    POSTGRES_UNIQUE_ERROR = psycopg.errors.UniqueViolation
except ImportError:
    psycopg = None
    dict_row = None

    class POSTGRES_UNIQUE_ERROR(Exception):
        """Fallback sentinel for SQLite-only environments."""


def is_postgres_dsn(database_url: str) -> bool:
    return database_url.startswith(('postgresql://', 'postgres://'))


def _driver():
    if psycopg is None:
        raise RuntimeError('PostgreSQL requires psycopg 3: pip install "psycopg[binary]>=3.2,<4"')
    return psycopg


def convert_internal_sql(sql: str) -> str:
    """Convert repository SQL, not user-supplied queries or identifiers."""
    return sql.replace('instr(', 'strpos(').replace('?', '%s')


class _MappedRow(dict):
    """Preserve the existing repository's mapping and integer-index reads."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _mapped_row(raw: dict[str, Any] | None):
    if raw is None:
        return None
    return _MappedRow({key: (
        str(value) if isinstance(value, uuid.UUID)
        else value.isoformat() if isinstance(value, (datetime, date))
        else value
    ) for key, value in raw.items()})


class _Cursor:
    def __init__(self, raw):
        self.raw = raw

    @property
    def rowcount(self):
        return self.raw.rowcount

    def fetchone(self):
        return _mapped_row(self.raw.fetchone())

    def fetchall(self):
        return [_mapped_row(row) for row in self.raw.fetchall()]


class _Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=()):
        if ('INSERT INTO audit_events' in sql or
                'INSERT INTO platform_audit_events' in sql):
            from psycopg.types.json import Jsonb
            params = (*params[:-1], Jsonb(json.loads(params[-1])))
        return _Cursor(self.raw.execute(convert_internal_sql(sql), params))


@contextmanager
def postgres_session(dsn: str):
    pg = _driver()
    with pg.connect(dsn, row_factory=dict_row, connect_timeout=5) as raw:
        yield _Connection(raw)


def postgres_initialize(dsn: str, default_plan_id: str,
                        trial_duration_seconds: int):
    import time

    pg = _driver()
    with pg.connect(dsn, row_factory=dict_row, connect_timeout=5) as raw:
        try:
            versions = {row['version'] for row in raw.execute(
                'SELECT version FROM schema_migrations'
            ).fetchall()}
        except pg.errors.UndefinedTable:
            raise RuntimeError(
                'PostgreSQL schema missing; apply migrations 001 through 004 first'
            ) from None
        if not {'001_initial', '002_user_management', '003_sessions_invitations',
                '004_security_delivery'}.issubset(versions):
            raise RuntimeError('PostgreSQL migrations 001 through 004 are required')
        raw.execute(
            'INSERT INTO subscription_plans '
            '(id,code,name,price_halalas,max_employees) '
            "VALUES (%s,'starter-trial','Starter Trial',0,25) ON CONFLICT DO NOTHING",
            (default_plan_id,),
        )
        raw.execute(
            'INSERT INTO organization_subscriptions '
            '(organization_id,plan_id,status,period_ends_at) '
            "SELECT id,%s,'trialing',%s FROM organizations WHERE TRUE "
            'ON CONFLICT (organization_id) DO NOTHING',
            (default_plan_id, int(time.time()) + trial_duration_seconds),
        )
