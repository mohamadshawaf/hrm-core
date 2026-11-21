"""Company owner-only user management and tenant boundary tests."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.database import session
from app.main import create_app


SECRET = 'company-user-contract-tests-private-key-123456'
PASSWORD = 'temporary-password-for-testing-1234'


class CompanyUserTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'tenants.sqlite3')
        self.alpha_id, self.alpha_owner_id = create_organization_owner(
            self.db, code='alpha', name='Alpha Business',
            email='boss@alpha.example', password=PASSWORD,
        )
        self.beta_id, _ = create_organization_owner(
            self.db, code='beta', name='Beta Business',
            email='boss@beta.example', password=PASSWORD,
        )
        # Legacy compatibility regression: new deployments require invitations.
        self.client = TestClient(create_app(database_path=self.db, jwt_secret=SECRET,
                                            allow_legacy_user_creation=True))
        self.client.__enter__()
        self.alpha = self.login('alpha', 'boss@alpha.example')
        self.beta = self.login('beta', 'boss@beta.example')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self, org: str, email: str):
        response = self.client.post('/api/v1/auth/token', json={
            'organization_code': org, 'email': email, 'password': PASSWORD,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def add_user(self, email='member@alpha.example', role='hr'):
        return self.client.post('/api/v1/organization/users', headers=self.alpha,
                                json={'email': email, 'password': PASSWORD, 'role': role})

    def test_owner_creates_hr_and_viewer_and_sees_only_own_users(self):
        new_user = self.add_user()
        self.assertEqual(new_user.status_code, 201, new_user.text)
        self.assertTrue(new_user.json()['is_active'])
        self.assertEqual(new_user.json()['version'], 1)
        self.assertNotIn('password', json.dumps(new_user.json()))
        alpha_page = self.client.get('/api/v1/organization/users', headers=self.alpha)
        beta_page = self.client.get('/api/v1/organization/users', headers=self.beta)
        self.assertEqual(alpha_page.json()['total'], 2)
        self.assertEqual(beta_page.json()['total'], 1)
        self.assertEqual(self.login('alpha', 'member@alpha.example') is not None, True)

    def test_credential_and_role_escalation_rejected(self):
        self.assertEqual(self.add_user(role='owner').status_code, 422)
        self.assertEqual(self.add_user(role='platform_owner').status_code, 422)
        self.assertEqual(self.add_user().status_code, 201)
        self.assertEqual(self.add_user(email='MEMBER@ALPHA.EXAMPLE').status_code, 409)
        self.assertEqual(self.client.post('/api/v1/organization/users',
                                          headers=self.alpha,
                                          json={'email': 'other@example.com',
                                                'password': 'weak', 'role': 'hr'}).status_code, 422)

    def test_hr_and_viewer_cannot_manage_accounts(self):
        member = self.add_user().json()
        hr_header = self.login('alpha', member['email'])
        self.assertEqual(self.client.get('/api/v1/organization/users',
                                         headers=hr_header).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/organization/users', headers=hr_header,
                                          json={'email': 'test@example.org',
                                                'password': PASSWORD, 'role': 'viewer'}).status_code, 403)
        self.assertEqual(self.client.patch(
            f"/api/v1/organization/users/{member['id']}", headers=hr_header,
            json={'expected_version': 1, 'role': 'viewer'},
        ).status_code, 403)

    def test_owner_account_is_protected_and_cross_company_isolation(self):
        member = self.add_user().json()
        endpoint = f"/api/v1/organization/users/{member['id']}"
        self.assertEqual(self.client.patch(endpoint, headers=self.beta,
                                           json={'expected_version': 1,
                                                 'is_active': False}).status_code, 404)
        self.assertEqual(self.client.patch(
            f'/api/v1/organization/users/{self.alpha_owner_id}',
            headers=self.alpha, json={'expected_version': 1,
                                      'is_active': False},
        ).status_code, 403)
        self.assertEqual(self.client.patch(
            f'/api/v1/organization/users/{uuid4()}',
            headers=self.alpha, json={'expected_version': 1,
                                      'role': 'hr'},
        ).status_code, 404)

    def test_deactivation_revokes_session_and_updates_are_versioned(self):
        member = self.add_user().json()
        member_header = self.login('alpha', member['email'])
        endpoint = f"/api/v1/organization/users/{member['id']}"
        changed = self.client.patch(endpoint, headers=self.alpha,
                                    json={'expected_version': 1, 'is_active': False})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()['version'], 2)
        self.assertFalse(changed.json()['is_active'])
        self.assertEqual(self.client.get('/api/v1/auth/me',
                                         headers=member_header).status_code, 401)
        self.assertEqual(self.client.patch(endpoint, headers=self.alpha,
                                           json={'expected_version': 1,
                                                 'role': 'viewer'}).status_code, 409)
        self.assertEqual(self.client.patch(endpoint, headers=self.alpha,
                                           json={'expected_version': 2,
                                                 'role': None}).status_code, 422)
        self.assertEqual(self.client.patch(endpoint, headers=self.alpha,
                                           json={'expected_version': 2,
                                                 'role': 'viewer', 'is_active': True}).status_code, 200)
        with session(self.db) as connection:
            events = connection.execute(
                "SELECT action,changed_fields FROM audit_events WHERE entity_type='user' "
                'ORDER BY rowid',
            ).fetchall()
        self.assertEqual([row['action'] for row in events], ['create', 'update', 'update'])
        self.assertNotIn('password_hash', ''.join(row['changed_fields'] for row in events))


if __name__ == '__main__':
    unittest.main()
