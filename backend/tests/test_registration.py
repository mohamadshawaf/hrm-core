"""Self-service registration contract, isolation and verification safeguards."""

import hashlib
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.database import initialize, session
from app.main import create_app


SECRET = 'register-tests-are-not-production-secret-123456789'
PASSWORD = 'long-unique-registration-password-123'


class RegistrationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / 'registration.db')
        self.sent = []
        self.app = create_app(
            database_path=self.db_path, jwt_secret=SECRET,
            verification_sender=lambda email, token: self.sent.append((email, token)),
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def register(self, code='acme', email='Owner@Example.org'):
        return self.client.post('/api/v1/organizations/register', json={
            'organization_code': code,
            'organization_name': 'Example Consulting Co.',
            'owner_email': email,
            'password': PASSWORD,
        })

    def login(self, code='acme'):
        return self.client.post('/api/v1/auth/token', json={
            'organization_code': code, 'email': 'owner@example.org',
            'password': PASSWORD,
        })

    def activate(self, token=None):
        return self.client.post('/api/v1/organizations/verify-email', json={
            'token': token if token is not None else self.sent[-1][1],
        })

    def test_register_is_pending_until_email_verified(self):
        response = self.register()
        self.assertEqual(response.status_code, 202, response.text)
        self.assertNotIn('token', str(response.json()))
        self.assertEqual(self.sent[0][0], 'owner@example.org')
        self.assertEqual(self.login().status_code, 401)
        with session(self.db_path) as connection:
            row = connection.execute('SELECT status FROM organizations WHERE code=?', ('acme',)).fetchone()
            stored = connection.execute('SELECT token_hash FROM email_verifications').fetchone()[0]
            self.assertEqual(row['status'], 'pending_email')
            self.assertNotEqual(stored, self.sent[0][1])
            self.assertEqual(stored, hashlib.sha256(self.sent[0][1].encode()).hexdigest())
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_one_time_code_and_invalid_code(self):
        self.register()
        self.assertEqual(self.activate('z' * 45).status_code, 400)
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.activate().status_code, 400)

    def test_expired_code_never_activates(self):
        self.register()
        with session(self.db_path) as connection:
            connection.execute('UPDATE email_verifications SET expires_at=0')
        self.assertEqual(self.activate().status_code, 400)
        self.assertEqual(self.login().status_code, 401)

    def test_resend_after_expiry_invalidates_old_code(self):
        self.register()
        old_token = self.sent[-1][1]
        with session(self.db_path) as connection:
            connection.execute('UPDATE email_verifications SET issued_at=0, expires_at=0')
        result = self.client.post('/api/v1/organizations/resend-verification', json={
            'organization_code': 'acme', 'owner_email': 'owner@example.org',
        })
        self.assertEqual(result.status_code, 202)
        self.assertEqual(len(self.sent), 2)
        self.assertNotEqual(old_token, self.sent[-1][1])
        self.assertEqual(self.activate(old_token).status_code, 400)
        self.assertEqual(self.activate().status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_resend_cooldown_and_unknown_account_use_generic_response(self):
        self.register()
        original = self.client.post('/api/v1/organizations/resend-verification', json={
            'organization_code': 'acme', 'owner_email': 'owner@example.org',
        })
        unknown = self.client.post('/api/v1/organizations/resend-verification', json={
            'organization_code': 'no-such-company', 'owner_email': 'owner@example.org',
        })
        self.assertEqual(original.status_code, 202)
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(original.json(), unknown.json())
        self.assertEqual(len(self.sent), 1)

    def test_duplicate_code_does_not_create_more_users(self):
        self.assertEqual(self.register().status_code, 202)
        self.assertEqual(self.register(email='other@example.org').status_code, 409)
        self.assertEqual(len(self.sent), 1)
        with session(self.db_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM organizations').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_validation_and_no_public_role_assignment(self):
        payload = {
            'organization_code': 'UPPER CASE', 'organization_name': '',
            'owner_email': 'not-email', 'password': 'too-short', 'role': 'superadmin',
        }
        self.assertEqual(self.client.post('/api/v1/organizations/register', json=payload).status_code, 422)
        self.assertEqual(self.sent, [])

    def test_suspending_company_revokes_existing_token(self):
        self.register()
        self.activate()
        token = self.login().json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=headers).status_code, 200)
        with session(self.db_path) as connection:
            connection.execute("UPDATE organizations SET status='suspended' WHERE code='acme'")
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=headers).status_code, 401)

    def test_delivery_failure_rolls_back_registration(self):
        broken = TestClient(create_app(
            database_path=self.db_path, jwt_secret=SECRET,
            verification_sender=lambda _email, _token: (_ for _ in ()).throw(OSError('email failed')),
        ))
        result = broken.post('/api/v1/organizations/register', json={
            'organization_code': 'failed', 'organization_name': 'Failed Org',
            'owner_email': 'admin@example.org', 'password': PASSWORD,
        })
        self.assertEqual(result.status_code, 503, result.text)
        self.assertNotIn('email failed', result.text)
        with session(self.db_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM organizations').fetchone()[0], 0)

    def test_independent_companies_get_isolated_records(self):
        self.assertEqual(self.register('alpha').status_code, 202)
        self.activate()
        alpha_headers = {'Authorization': 'Bearer ' + self.login('alpha').json()['access_token']}
        self.assertEqual(self.register('beta').status_code, 202)
        self.activate()
        beta_headers = {'Authorization': 'Bearer ' + self.login('beta').json()['access_token']}
        employee = self.client.post('/api/v1/employees', headers=alpha_headers, json={
            'employee_code': 'EMP-100', 'full_name': 'Employee A',
            'job_title': 'Analyst', 'department': 'Finance', 'hire_date': '2024-01-01',
        })
        self.assertEqual(employee.status_code, 201, employee.text)
        self.assertEqual(self.client.get('/api/v1/employees', headers=beta_headers).json()['total'], 0)
        self.assertEqual(self.client.get('/api/v1/employees/' + employee.json()['id'],
                                         headers=beta_headers).status_code, 404)


class LegacyDatabaseUpgradeTests(unittest.TestCase):
    def test_milestone_one_database_gets_active_org_status(self):
        with TemporaryDirectory() as temp:
            path = str(Path(temp) / 'legacy.db')
            with sqlite3.connect(path) as connection:
                connection.execute('CREATE TABLE organizations('
                                   'id TEXT PRIMARY KEY, code TEXT UNIQUE, name TEXT, created_at TEXT)')
                connection.execute("INSERT INTO organizations VALUES('old','old-org','Existing','2024-01-01')")
            initialize(path)
            with session(path) as connection:
                record = connection.execute(
                    "SELECT status FROM organizations WHERE code='old-org'"
                ).fetchone()
                self.assertEqual(record['status'], 'active')


if __name__ == '__main__':
    unittest.main()
