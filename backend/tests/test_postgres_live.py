"""Opt-in LIVE PostgreSQL smoke/integration test against a disposable schema.

This test never runs automatically against an unapproved external database.
Set both HRM_PG_TEST_ALLOW_SCHEMA_CREATE=1 and HRM_TEST_POSTGRES_DSN to a
dedicated, disposable PostgreSQL test database with CREATE SCHEMA permission.
"""

import os
from pathlib import Path
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.mail_queue import parse_mail_key
from app.mail_worker import process_one
from app.main import create_app


ENABLED = (os.getenv('HRM_PG_TEST_ALLOW_SCHEMA_CREATE') == '1' and
           bool(os.getenv('HRM_TEST_POSTGRES_DSN')))


@unittest.skipUnless(ENABLED, 'Live PostgreSQL test requires explicit disposable DB opt-in')
class LivePostgresTests(unittest.TestCase):
    def test_migrations_sessions_and_audit_on_real_postgres(self):
        try:
            import psycopg
            from psycopg import conninfo, sql
        except ImportError:
            self.skipTest('Install psycopg[binary] in the test environment')

        master_dsn = os.environ['HRM_TEST_POSTGRES_DSN']
        schema_name = 'hrm_test_' + uuid4().hex
        migrations = Path(__file__).resolve().parents[1] / 'postgres'
        # This schema is created by this test and dropped in finally; no
        # tables outside the temporary schema are touched by these migrations.
        with psycopg.connect(master_dsn, autocommit=True) as master:
            master.execute(sql.SQL('CREATE SCHEMA {}').format(
                sql.Identifier(schema_name)))
        try:
            schema_dsn = conninfo.make_conninfo(
                master_dsn, options=f'-c search_path={schema_name}')
            with psycopg.connect(schema_dsn, autocommit=True) as db:
                for filename in ('001_initial.sql', '002_user_management.sql',
                                 '003_sessions_invitations.sql',
                                 '004_security_delivery.sql'):
                    db.execute((migrations / filename).read_text(encoding='utf-8'))

            secret = 'postgres-test-signing-secret-with-enough-bytes-for-testing'
            password = 'strong-postgres-password-123456'
            create_organization_owner(schema_dsn, code='alpha', name='Alpha',
                                      email='owner@alpha.test', password=password)
            with TestClient(create_app(database_path=schema_dsn,
                                       jwt_secret=secret,
                                       mail_outbox_key='b5' * 32,
                                       invitation_sender=lambda *_: None)) as client:
                login = client.post('/api/v1/auth/token', json={
                    'organization_code': 'alpha', 'email': 'owner@alpha.test',
                    'password': password})
                self.assertEqual(login.status_code, 200, login.text)
                access = login.json()['access_token']
                headers = {'Authorization': 'Bearer ' + access}
                employee = client.post('/api/v1/employees', headers=headers, json={
                    'employee_code': 'E-001', 'full_name': 'Postgres Test',
                    'job_title': 'Engineer', 'department': 'Engineering',
                    'hire_date': '2025-01-01'})
                self.assertEqual(employee.status_code, 201, employee.text)
                self.assertEqual(client.get('/api/v1/employees',
                                            headers=headers).json()['total'], 1)
                delivered = []
                invited = client.post('/api/v1/organization/invitations',
                    headers=headers, json={'email': 'staff@alpha.test', 'role': 'viewer'})
                self.assertEqual(invited.status_code, 202, invited.text)
                self.assertTrue(process_one(schema_dsn, parse_mail_key('b5' * 32), {
                    'verification': lambda *_: None,
                    'invitation': lambda address, code, token: delivered.append(token),
                    'reset': lambda *_: None,
                }))
                self.assertEqual(len(delivered), 1)
                self.assertEqual(client.post('/api/v1/organization/invitations/accept',
                    json={'token': delivered[0], 'password': password}).status_code, 201)
                rotated = client.post('/api/v1/auth/refresh', json={
                    'refresh_token': login.json()['refresh_token']})
                self.assertEqual(rotated.status_code, 200, rotated.text)
                self.assertEqual(client.post('/api/v1/auth/logout', headers={
                    'Authorization': 'Bearer ' + rotated.json()['access_token']}).status_code, 204)
                self.assertEqual(client.get('/api/v1/auth/me', headers=headers).status_code, 401)
        finally:
            with psycopg.connect(master_dsn, autocommit=True) as master:
                master.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(
                    sql.Identifier(schema_name)))
