"""Postgres adapter contract checks independent of a running database."""

from datetime import datetime, timezone
import importlib.util
import unittest
from uuid import UUID

from app.database import initialize, session
from app.postgres_adapter import (_Connection, convert_internal_sql,
                                  is_postgres_dsn)


class FakeCursor:
    rowcount = 1

    def fetchone(self):
        return {'id': UUID('00000000-0000-4000-8000-000000000001'),
                'created_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'active': True}


class FakeConnection:
    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params
        return FakeCursor()


class PostgresAdapterTests(unittest.TestCase):
    def test_pg_query_placeholder_translation_and_mapping(self):
        self.assertTrue(is_postgres_dsn('postgresql://localhost/example'))
        self.assertFalse(is_postgres_dsn('./data/hrm.db'))
        fake = FakeConnection()
        cursor = _Connection(fake).execute(
            'SELECT * FROM users WHERE instr(lower(email),lower(?))>0 AND id=?',
            ('foo', 'id'),
        )
        self.assertIn('strpos(lower(email),lower(%s))', fake.last_sql)
        self.assertEqual(fake.last_sql.count('%s'), 2)
        self.assertEqual(fake.last_params, ('foo', 'id'))
        row = cursor.fetchone()
        self.assertEqual(row[0], row['id'])
        self.assertIsInstance(row['id'], str)
        self.assertIn('2025-01-01', row['created_at'])

    def test_unsupported_database_scheme_is_rejected(self):
        with self.assertRaises(RuntimeError):
            initialize('mysql://not-supported')

    @unittest.skipIf(importlib.util.find_spec('psycopg') is not None,
                     'Driver installed; integration requires a disposable PG instance')
    def test_missing_postgres_driver_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'psycopg'):
            with session('postgresql://localhost/never-connect'):
                pass


if __name__ == '__main__':
    unittest.main()
