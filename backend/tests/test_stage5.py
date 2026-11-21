"""Security contracts for milestone 5: invitations, rotation, revocation, limits."""

from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.database import session
from app.main import create_app


SECRET = 'milestone-five-private-test-secret-with-adequate-length'
PASSWORD = 'strong-password-for-the-local-test-123'


class StageFiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'hrm.sqlite')
        self.alpha_id, self.owner_id = create_organization_owner(
            self.db, code='alpha', name='Alpha', email='owner@alpha.test', password=PASSWORD)
        self.beta_id, self.beta_owner_id = create_organization_owner(
            self.db, code='beta', name='Beta', email='owner@beta.test', password=PASSWORD)
        self.delivered = []
        self.reset_delivered = []
        self.client = TestClient(create_app(
            database_path=self.db, jwt_secret=SECRET,
            invitation_sender=lambda email, code, token: self.delivered.append(
                (email, code, token)),
            password_reset_sender=lambda email, code, token: self.reset_delivered.append(
                (email, code, token))))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self, company='alpha', email=None, client=None):
        target = client or self.client
        return target.post('/api/v1/auth/token', json={
            'organization_code': company,
            'email': email or f'owner@{company}.test',
            'password': PASSWORD,
            'device_label': 'Security contract test',
        })

    def headers(self, company='alpha'):
        response = self.login(company)
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def employee(self, code):
        return {'employee_code': code, 'full_name': 'Testing Employee',
                'job_title': 'Engineer', 'department': 'Engineering',
                'hire_date': '2025-01-02', 'status': 'active'}

    def test_rotating_refresh_and_replay_revokes_device(self):
        first = self.login().json()
        self.assertGreaterEqual(len(first['refresh_token']), 32)
        rotated = self.client.post('/api/v1/auth/refresh', json={
            'refresh_token': first['refresh_token']})
        self.assertEqual(rotated.status_code, 200, rotated.text)
        new = rotated.json()
        self.assertNotEqual(first['refresh_token'], new['refresh_token'])
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={
            'Authorization': 'Bearer ' + new['access_token']}).status_code, 200)
        replay = self.client.post('/api/v1/auth/refresh', json={
            'refresh_token': first['refresh_token']})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', json={
            'refresh_token': new['refresh_token']}).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={
            'Authorization': 'Bearer ' + new['access_token']}).status_code, 401)

    def test_sessions_revocable_and_cross_company_hidden(self):
        first = self.login().json()
        second = self.login().json()
        auth = {'Authorization': 'Bearer ' + first['access_token']}
        sessions = self.client.get('/api/v1/auth/sessions', headers=auth)
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(len(sessions.json()['items']), 2)
        self.assertEqual(sum(bool(i['is_current']) for i in sessions.json()['items']), 1)
        other_id = next(i['id'] for i in sessions.json()['items'] if not i['is_current'])
        self.assertEqual(self.client.delete('/api/v1/auth/sessions/' + other_id,
                                            headers=self.headers('beta')).status_code, 404)
        self.assertEqual(self.client.delete('/api/v1/auth/sessions/' + other_id,
                                            headers=auth).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={
            'Authorization': 'Bearer ' + second['access_token']}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/logout-all', headers=auth).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=auth).status_code, 401)

    def test_current_logout_revokes_access_and_refresh(self):
        data = self.login().json()
        auth = {'Authorization': 'Bearer ' + data['access_token']}
        self.assertEqual(self.client.post('/api/v1/auth/logout', headers=auth).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=auth).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', json={
            'refresh_token': data['refresh_token']}).status_code, 401)

    def test_invitation_is_one_time_tenant_scoped_and_owner_only(self):
        owner = self.headers()
        invited = self.client.post('/api/v1/organization/invitations', headers=owner,
                                   json={'email': 'staff@alpha.test', 'role': 'hr'})
        self.assertEqual(invited.status_code, 202, invited.text)
        self.assertNotIn('token', str(invited.json()))
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(self.delivered[0][:2], ('staff@alpha.test', 'alpha'))
        secret = self.delivered[0][2]
        self.assertEqual(self.client.post('/api/v1/organization/invitations/accept',
                                         json={'token': secret, 'password': PASSWORD}).status_code, 201)
        self.assertEqual(self.client.post('/api/v1/organization/invitations/accept',
                                         json={'token': secret, 'password': PASSWORD}).status_code, 400)
        self.assertEqual(self.login(email='staff@alpha.test').status_code, 200)
        self.assertEqual(self.login('beta', email='staff@alpha.test').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/organization/invitations',
                                         headers=self.headers('beta')).json()['items'], [])
        staff = self.login(email='staff@alpha.test').json()
        self.assertEqual(self.client.post('/api/v1/organization/invitations', headers={
            'Authorization': 'Bearer ' + staff['access_token']}, json={
            'email': 'other@alpha.test', 'role': 'viewer'}).status_code, 403)

    def test_invitation_cooldown_expiry_and_no_privilege_escalation(self):
        owner = self.headers()
        uri = '/api/v1/organization/invitations'
        self.assertEqual(self.client.post(uri, headers=owner, json={
            'email': 'other@alpha.test', 'role': 'owner'}).status_code, 422)
        self.assertEqual(self.client.post(uri, headers=owner, json={
            'email': 'other@alpha.test', 'role': 'viewer'}).status_code, 202)
        self.assertEqual(self.client.post(uri, headers=owner, json={
            'email': 'other@alpha.test', 'role': 'viewer'}).status_code, 429)
        with session(self.db) as connection:
            connection.execute('UPDATE user_invitations SET expires_at=? '
                               'WHERE organization_id=?', (int(time.time()) - 1, self.alpha_id))
        self.assertEqual(self.client.post(uri + '/accept', json={
            'token': self.delivered[0][2], 'password': PASSWORD}).status_code, 400)

    def test_legacy_password_creation_disabled_by_default(self):
        self.assertEqual(self.client.post('/api/v1/organization/users',
            headers=self.headers(), json={
                'email': 'staff@alpha.test', 'role': 'hr',
                'password': PASSWORD}).status_code, 410)

    def test_invitation_delivery_failure_rolls_back_record(self):
        client = TestClient(create_app(database_path=self.db, jwt_secret=SECRET,
            invitation_sender=lambda _a, _b, _c: (_ for _ in ()).throw(
                RuntimeError('SMTP unavailable'))))
        with client:
            owner = self.headers()
            failed = client.post('/api/v1/organization/invitations', headers=owner,
                                 json={'email': 'fail@alpha.test', 'role': 'viewer'})
            self.assertEqual(failed.status_code, 503)
        with session(self.db) as connection:
            count = connection.execute('SELECT COUNT(*) FROM user_invitations '
                                       'WHERE email=?', ('fail@alpha.test',)).fetchone()[0]
        self.assertEqual(count, 0)

    def test_subscription_is_opt_in_and_employee_limit_enforced(self):
        with session(self.db) as connection:
            connection.execute('UPDATE subscription_plans SET max_employees=1 '
                               'WHERE code=?', ('starter-trial',))
        enforced = TestClient(create_app(database_path=self.db, jwt_secret=SECRET,
                                        enforce_subscriptions=True))
        with enforced:
            login = self.login(client=enforced)
            self.assertEqual(login.status_code, 200)
            owner = {'Authorization': 'Bearer ' + login.json()['access_token']}
            first = enforced.post('/api/v1/employees', headers=owner,
                                  json=self.employee('EMP-001'))
            self.assertEqual(first.status_code, 201, first.text)
            second = enforced.post('/api/v1/employees', headers=owner,
                                   json=self.employee('EMP-002'))
            self.assertEqual(second.status_code, 409, second.text)
            self.assertIn('limit', second.json()['detail'].lower())
            self.assertEqual(enforced.delete('/api/v1/employees/' + first.json()['id'],
                params={'expected_version': 1}, headers=owner).status_code, 204)
            self.assertEqual(enforced.post('/api/v1/employees', headers=owner,
                json=self.employee('EMP-002')).status_code, 201)
            with session(self.db) as connection:
                connection.execute('UPDATE organization_subscriptions SET status=? '
                                   'WHERE organization_id=?', ('past_due', self.alpha_id))
            self.assertEqual(enforced.get('/api/v1/auth/me', headers=owner).status_code, 403)
            self.assertEqual(self.login(client=enforced).status_code, 403)
            # Default policy is advisory, pending explicit commercial approval.
            self.assertEqual(self.login().status_code, 200)

    def test_expired_trial_rejected_only_when_enabled(self):
        with session(self.db) as connection:
            connection.execute('UPDATE organization_subscriptions SET period_ends_at=? '
                               'WHERE organization_id=?', (int(time.time()) - 10, self.alpha_id))
        enforced = TestClient(create_app(database_path=self.db, jwt_secret=SECRET,
                                        enforce_subscriptions=True))
        with enforced:
            self.assertEqual(self.login(client=enforced).status_code, 403)
        self.assertEqual(self.login().status_code, 200)

    def test_password_reset_is_one_time_and_revokes_all_device_sessions(self):
        first = self.login().json()
        second = self.login().json()
        uri = '/api/v1/auth/password-resets'
        requested = self.client.post(uri + '/request', json={
            'organization_code': 'alpha', 'email': 'OWNER@ALPHA.TEST'})
        self.assertEqual(requested.status_code, 202)
        self.assertEqual(len(self.reset_delivered), 1)
        self.assertNotIn('token', str(requested.json()))
        token = self.reset_delivered[0][2]
        new_password = 'different-strong-password-for-testing-789'
        completed = self.client.post(uri + '/confirm', json={
            'token': token, 'new_password': new_password})
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(self.client.post(uri + '/confirm', json={
            'token': token, 'new_password': new_password}).status_code, 400)
        for session_data in (first, second):
            self.assertEqual(self.client.get('/api/v1/auth/me', headers={
                'Authorization': 'Bearer ' + session_data['access_token']}).status_code, 401)
            self.assertEqual(self.client.post('/api/v1/auth/refresh', json={
                'refresh_token': session_data['refresh_token']}).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/token', json={
            'organization_code': 'alpha', 'email': 'owner@alpha.test',
            'password': new_password}).status_code, 200)

    def test_password_reset_is_non_enumerating_rate_limited_and_expires(self):
        uri = '/api/v1/auth/password-resets'
        unknown = self.client.post(uri + '/request', json={
            'organization_code': 'alpha', 'email': 'unknown@alpha.test'})
        known = self.client.post(uri + '/request', json={
            'organization_code': 'alpha', 'email': 'owner@alpha.test'})
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.json(), known.json())
        self.assertEqual(self.client.post(uri + '/request', json={
            'organization_code': 'alpha', 'email': 'owner@alpha.test'}).status_code, 202)
        self.assertEqual(len(self.reset_delivered), 1)
        with session(self.db) as connection:
            connection.execute('UPDATE password_resets SET expires_at=?',
                               (int(time.time()) - 1,))
        self.assertEqual(self.client.post(uri + '/confirm', json={
            'token': self.reset_delivered[0][2],
            'new_password': 'new-strong-password-12345'}).status_code, 400)

    def test_failed_password_reset_delivery_preserves_existing_token(self):
        uri = '/api/v1/auth/password-resets/request'
        self.assertEqual(self.client.post(uri, json={
            'organization_code': 'alpha', 'email': 'owner@alpha.test'}).status_code, 202)
        original = self.reset_delivered[0][2]
        with session(self.db) as connection:
            connection.execute('UPDATE password_resets SET created_at=?',
                               (int(time.time()) - 90,))
        broken_client = TestClient(create_app(database_path=self.db,
            jwt_secret=SECRET, password_reset_sender=lambda *_: (_ for _ in ()).throw(
                RuntimeError('mail unavailable'))))
        with broken_client:
            response = broken_client.post(uri, json={
                'organization_code': 'alpha', 'email': 'owner@alpha.test'})
            self.assertEqual(response.status_code, 202)
        self.assertEqual(self.client.post('/api/v1/auth/password-resets/confirm',
            json={'token': original, 'new_password': 'other-strong-password-1234'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
