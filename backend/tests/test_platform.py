"""Platform-only authorization, multi-tenant control and subscription metadata."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.database import session
from app.main import create_app
from app.platform_bootstrap import create_platform_owner


TENANT_SECRET = 'unique-tenant-key-for-platform-integration-tests-123'
PLATFORM_SECRET = 'separate-platform-key-for-integration-tests-4567'
PASSWORD = 'strong-password-used-only-in-tests-123'


class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'platform.sqlite3')
        self.alpha_id, _ = create_organization_owner(
            self.db, code='alpha', name='Alpha Business',
            email='owner@alpha.example', password=PASSWORD,
        )
        self.beta_id, _ = create_organization_owner(
            self.db, code='beta', name='Beta Business',
            email='owner@beta.example', password=PASSWORD,
        )
        self.platform_id = create_platform_owner(
            self.db, email='Admin@Platform.example', password=PASSWORD,
        )
        self.client = TestClient(create_app(
            database_path=self.db,
            jwt_secret=TENANT_SECRET,
            platform_jwt_secret=PLATFORM_SECRET,
            verification_sender=lambda _email, _token: None,
        ))
        self.client.__enter__()
        response = self.client.post('/api/v1/platform/auth/token', json={
            'email': 'ADMIN@PLATFORM.EXAMPLE', 'password': PASSWORD,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.platform_token = response.json()['access_token']
        self.platform_headers = {'Authorization': f'Bearer {self.platform_token}'}
        owner = self.client.post('/api/v1/auth/token', json={
            'organization_code': 'alpha', 'email': 'owner@alpha.example',
            'password': PASSWORD,
        })
        self.assertEqual(owner.status_code, 200, owner.text)
        self.tenant_headers = {'Authorization': f"Bearer {owner.json()['access_token']}"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def test_platform_and_tenant_tokens_are_never_interchangeable(self):
        self.assertEqual(self.client.get('/api/v1/platform/overview').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/platform/overview',
                                         headers=self.tenant_headers).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/employees',
                                         headers=self.platform_headers).status_code, 401)
        identity = self.client.get('/api/v1/platform/auth/me', headers=self.platform_headers)
        self.assertEqual(identity.json()['role'], 'platform_owner')

    def test_overview_and_company_search_no_employee_details(self):
        overview = self.client.get('/api/v1/platform/overview', headers=self.platform_headers)
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()['organizations_total'], 2)
        self.assertEqual(overview.json()['organizations_active'], 2)
        listing = self.client.get('/api/v1/platform/organizations?search=alpha',
                                  headers=self.platform_headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()['total'], 1)
        self.assertEqual(listing.json()['items'][0]['id'], self.alpha_id)
        self.assertEqual(listing.json()['items'][0]['plan_name'], 'Starter Trial')
        self.assertEqual(listing.json()['items'][0]['subscription_version'], 1)
        self.assertNotIn('password_hash', json.dumps(listing.json()))

    def test_tenant_owner_cannot_control_platform(self):
        status_url = f'/api/v1/platform/organizations/{self.beta_id}/status'
        self.assertEqual(self.client.patch(status_url, headers=self.tenant_headers,
                                           json={'status': 'suspended'}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/platform/plans',
                                          headers=self.tenant_headers, json={
            'code': 'advanced', 'name': 'Advanced',
            'price_halalas': 10000, 'max_employees': 100,
        }).status_code, 401)

    def test_suspend_revokes_tenant_token_and_reactivation(self):
        endpoint = f'/api/v1/platform/organizations/{self.alpha_id}/status'
        response = self.client.patch(endpoint, json={'status': 'suspended'},
                                     headers=self.platform_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['changed'])
        self.assertEqual(self.client.get('/api/v1/auth/me',
                                         headers=self.tenant_headers).status_code, 401)
        resumed = self.client.patch(endpoint, json={'status': 'active'},
                                    headers=self.platform_headers)
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me',
                                         headers=self.tenant_headers).status_code, 200)
        with session(self.db) as connection:
            audits = connection.execute(
                "SELECT changed_fields FROM platform_audit_events "
                "WHERE action='organization_status' ORDER BY rowid",
            ).fetchall()
        self.assertEqual(len(audits), 2)
        self.assertEqual(json.loads(audits[0]['changed_fields']), ['status'])

    def test_pending_email_company_cannot_be_activated_by_admin(self):
        registration = self.client.post('/api/v1/organizations/register', json={
            'organization_code': 'pending', 'organization_name': 'Pending Business',
            'owner_email': 'pending@example.org', 'password': PASSWORD,
        })
        self.assertEqual(registration.status_code, 202)
        listing = self.client.get('/api/v1/platform/organizations?search=pending',
                                  headers=self.platform_headers).json()['items']
        company_id = listing[0]['id']
        response = self.client.patch(f'/api/v1/platform/organizations/{company_id}/status',
                                     headers=self.platform_headers, json={'status': 'active'})
        self.assertEqual(response.status_code, 409)
        with session(self.db) as connection:
            status = connection.execute('SELECT status FROM organizations WHERE id=?',
                                        (company_id,)).fetchone()['status']
        self.assertEqual(status, 'pending_email')

    def test_plan_creation_validation_and_duplicate_code(self):
        payload = {'code': 'growth', 'name': 'Growth Plan',
                   'price_halalas': 29900, 'max_employees': 200}
        made = self.client.post('/api/v1/platform/plans', json=payload,
                                headers=self.platform_headers)
        self.assertEqual(made.status_code, 201, made.text)
        self.assertEqual(made.json()['price_halalas'], 29900)
        self.assertEqual(self.client.post('/api/v1/platform/plans', json=payload,
                                          headers=self.platform_headers).status_code, 409)
        self.assertEqual(self.client.post('/api/v1/platform/plans',
                                          json={**payload, 'price_halalas': -10},
                                          headers=self.platform_headers).status_code, 422)

    def test_subscription_optimistic_lock_and_audit(self):
        made = self.client.post('/api/v1/platform/plans', headers=self.platform_headers,
                                json={'code': 'business', 'name': 'Business Plan',
                                      'price_halalas': 50000, 'max_employees': 300})
        plan_id = made.json()['id']
        url = f'/api/v1/platform/organizations/{self.alpha_id}/subscription'
        payload = {
            'plan_id': plan_id, 'status': 'active',
            'period_ends_at': int(time.time()) + 30 * 86400,
            'expected_version': 1,
        }
        response = self.client.patch(url, json=payload, headers=self.platform_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.patch(url, json=payload,
                                           headers=self.platform_headers).status_code, 409)
        listing = self.client.get('/api/v1/platform/organizations?search=alpha',
                                  headers=self.platform_headers).json()['items'][0]
        self.assertEqual(listing['plan_name'], 'Business Plan')
        self.assertEqual(listing['subscription_status'], 'active')
        self.assertEqual(listing['subscription_version'], 2)
        with session(self.db) as connection:
            events = connection.execute(
                "SELECT action,changed_fields FROM platform_audit_events "
                "WHERE organization_id=?", (self.alpha_id,),
            ).fetchall()
        self.assertEqual([row['action'] for row in events], ['subscription_update'])
        self.assertEqual(json.loads(events[0]['changed_fields']),
                         ['period_ends_at', 'plan_id', 'status'])

    def test_disabled_platform_admin_rejects_issued_token(self):
        with session(self.db) as connection:
            connection.execute('UPDATE platform_admins SET is_active=0 WHERE id=?',
                               (self.platform_id,))
        self.assertEqual(self.client.get('/api/v1/platform/overview',
                                         headers=self.platform_headers).status_code, 401)

    def test_platform_admin_secret_is_required_and_distinct(self):
        with self.assertRaises(RuntimeError):
            create_app(database_path=self.db, jwt_secret=TENANT_SECRET,
                       platform_jwt_secret=TENANT_SECRET)
        without_admin = TestClient(create_app(
            database_path=self.db, jwt_secret=TENANT_SECRET,
            platform_jwt_secret='',
        ))
        self.assertEqual(without_admin.post('/api/v1/platform/auth/token', json={
            'email': 'admin@platform.example', 'password': PASSWORD,
        }).status_code, 503)

    def test_platform_input_constrains_status_and_unknown_org(self):
        url = f'/api/v1/platform/organizations/{self.beta_id}/status'
        self.assertEqual(self.client.patch(url, headers=self.platform_headers,
                                           json={'status': 'pending_email'}).status_code, 422)
        self.assertEqual(self.client.patch(
            f'/api/v1/platform/organizations/{uuid4()}/status',
            headers=self.platform_headers, json={'status': 'active'},
        ).status_code, 404)


if __name__ == '__main__':
    unittest.main()
