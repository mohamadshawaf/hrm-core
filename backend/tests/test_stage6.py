"""Phase 6: persisted throttling, encrypted mail, retry, crash safety, cleanup."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
import time
import unittest

from fastapi.testclient import TestClient
from cryptography.exceptions import InvalidTag

from app.bootstrap import create_organization_owner
from app.database import session
from app.mail_queue import MailQueue, parse_mail_key
from app.mail_worker import process_one
from app.main import create_app
from app.maintenance import purge_expired
from app.rate_limiter import RateLimiter


SECRET = 'stage-six-local-test-secret-not-for-production-use'
PASSWORD = 'strong-test-password-for-stage-six-123'
KEY = 'b5' * 32


class StageSixTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'stage6.db')
        self.org, self.user = create_organization_owner(
            self.db, code='alpha', name='Alpha',
            email='owner@alpha.test', password=PASSWORD)

    def tearDown(self):
        self.temp.cleanup()

    def app(self, **kwargs):
        return TestClient(create_app(database_path=self.db, jwt_secret=SECRET,
                                     **kwargs))

    def owner(self, client):
        response = client.post('/api/v1/auth/token', json={
            'organization_code': 'alpha', 'email': 'owner@alpha.test',
            'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def senders(self, delivered):
        return {
            'verification': lambda email, token: delivered.append(
                ('verification', email, token)),
            'invitation': lambda email, code, token: delivered.append(
                ('invitation', email, code, token)),
            'reset': lambda email, code, token: delivered.append(
                ('reset', email, code, token)),
        }

    def test_rate_limiter_persists_across_requests_without_plaintext_subject(self):
        with session(self.db) as connection:
            limiter = RateLimiter(connection, SECRET)
            self.assertTrue(limiter.hit('login', '10.0.0.1:alice@example.com',
                                        limit=2, window_seconds=60, now=120))
            self.assertTrue(limiter.hit('login', '10.0.0.1:alice@example.com',
                                        limit=2, window_seconds=60, now=121))
        with session(self.db) as connection:
            limiter = RateLimiter(connection, SECRET)
            self.assertFalse(limiter.hit('login', '10.0.0.1:alice@example.com',
                                         limit=2, window_seconds=60, now=122))
            self.assertTrue(limiter.hit('login', '10.0.0.1:alice@example.com',
                                        limit=2, window_seconds=60, now=180))
            keys = [row[0] for row in connection.execute(
                'SELECT bucket_key FROM rate_limit_hits').fetchall()]
        self.assertEqual(len(keys), 2)
        self.assertTrue(all('alice' not in value and '10.0' not in value
                            for value in keys))

    def test_login_throttling_counters_survive_failed_password_transactions(self):
        with self.app() as client:
            body = {'organization_code': 'alpha', 'email': 'owner@alpha.test',
                    'password': 'incorrect-password-value'}
            for _ in range(15):
                response = client.post('/api/v1/auth/token', json=body)
                self.assertEqual(response.status_code, 401, response.text)
            throttled = client.post('/api/v1/auth/token', json=body)
            self.assertEqual(throttled.status_code, 429)
            self.assertEqual(throttled.headers['retry-after'], '60')

    def test_registration_code_queued_encrypted_and_delivered_only_after_commit(self):
        delivered = []
        with self.app(mail_outbox_key=KEY,
            verification_sender=lambda *_: (_ for _ in ()).throw(
                AssertionError('Synchronous email sender must not run'))) as client:
            registered = client.post('/api/v1/organizations/register', json={
                'organization_code': 'newco', 'organization_name': 'New Company',
                'owner_email': 'owner@newco.test', 'password': PASSWORD})
            self.assertEqual(registered.status_code, 202, registered.text)
            self.assertNotIn('token', str(registered.json()))
        with session(self.db) as connection:
            row = connection.execute('SELECT * FROM mail_outbox').fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['status'], 'pending')
            self.assertNotIn(b'owner@newco.test', bytes(row['ciphertext']))
            self.assertEqual(len(row['nonce']), 12)
        self.assertTrue(process_one(self.db, parse_mail_key(KEY), self.senders(delivered)))
        self.assertEqual(delivered[0][:2], ('verification', 'owner@newco.test'))
        with self.app() as client:
            activated = client.post('/api/v1/organizations/verify-email', json={
                'token': delivered[0][2]})
            self.assertEqual(activated.status_code, 200, activated.text)
        with session(self.db) as connection:
            sent = connection.execute('SELECT status,nonce,ciphertext FROM mail_outbox').fetchone()
            self.assertEqual(sent['status'], 'sent')
            self.assertIsNone(sent['nonce'])
            self.assertIsNone(sent['ciphertext'])

    def test_invitation_and_password_recovery_use_encrypted_outbox(self):
        delivered = []
        with self.app(mail_outbox_key=KEY) as client:
            headers = self.owner(client)
            invitation = client.post('/api/v1/organization/invitations',
                headers=headers, json={'email': 'staff@alpha.test', 'role': 'viewer'})
            self.assertEqual(invitation.status_code, 202, invitation.text)
            self.assertTrue(process_one(self.db, parse_mail_key(KEY),
                                        self.senders(delivered)))
            self.assertEqual(delivered[0][:3], ('invitation', 'staff@alpha.test', 'alpha'))
            accepted = client.post('/api/v1/organization/invitations/accept', json={
                'token': delivered[0][3], 'password': PASSWORD})
            self.assertEqual(accepted.status_code, 201, accepted.text)
            reset = client.post('/api/v1/auth/password-resets/request', json={
                'organization_code': 'alpha', 'email': 'staff@alpha.test'})
            self.assertEqual(reset.status_code, 202, reset.text)
            self.assertTrue(process_one(self.db, parse_mail_key(KEY),
                                        self.senders(delivered)))
            self.assertEqual(delivered[1][:3], ('reset', 'staff@alpha.test', 'alpha'))
            changed = client.post('/api/v1/auth/password-resets/confirm', json={
                'token': delivered[1][3], 'new_password': 'new-password-for-staff-123'})
            self.assertEqual(changed.status_code, 200, changed.text)

    def test_failed_send_is_retried_without_exposing_secret(self):
        key = parse_mail_key(KEY)
        with session(self.db) as connection:
            MailQueue(connection, key).enqueue(kind='verification',
                recipient='a@example.test', organization_code='alpha',
                token='private-secret-token-do-not-log')
        failing = self.senders([])
        failing['verification'] = lambda *_: (_ for _ in ()).throw(
            RuntimeError('fake smtp offline'))
        self.assertTrue(process_one(self.db, key, failing))
        with session(self.db) as connection:
            state = connection.execute('SELECT * FROM mail_outbox').fetchone()
            self.assertEqual(state['status'], 'pending')
            self.assertEqual(state['attempts'], 1)
            self.assertGreater(state['next_attempt_at'], int(time.time()))
            connection.execute('UPDATE mail_outbox SET next_attempt_at=?',
                               (int(time.time()) - 1,))
        delivered = []
        self.assertTrue(process_one(self.db, key, self.senders(delivered)))
        self.assertEqual(delivered[0][2], 'private-secret-token-do-not-log')
        self.assertFalse(process_one(self.db, key, self.senders(delivered)))

    def test_expired_metadata_cleanup_leaves_active_sessions_untouched(self):
        with self.app() as client:
            self.owner(client)
        before = int(time.time())
        with session(self.db) as connection:
            connection.execute('INSERT INTO rate_limit_hits VALUES (?,?,?,?)',
                               ('0' * 64, 100, 1, 101))
            connection.execute('UPDATE user_sessions SET expires_at=?',
                               (before - 8 * 86400,))
            cleanup = purge_expired(connection, now=before)
            self.assertEqual(cleanup['user_sessions'], 1)
            self.assertEqual(cleanup['rate_limit_hits'], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_ciphertext_rejects_wrong_key_and_recovers_expired_worker_lease(self):
        key = parse_mail_key(KEY)
        with session(self.db) as connection:
            queue = MailQueue(connection, key)
            queue.enqueue(kind='verification', recipient='test@alpha.test',
                          organization_code='alpha', token='one-time-secret')
            connection.execute('UPDATE mail_outbox SET next_attempt_at=?',
                               (int(time.time()) - 101,))
            old_claim = queue.claim(now=int(time.time()) - 100)
            self.assertIsNotNone(old_claim)
            with self.assertRaises(InvalidTag):
                MailQueue.decrypt_message(old_claim, b'\x00' * 32)
        received = []
        self.assertTrue(process_one(self.db, key, self.senders(received)))
        self.assertEqual(received, [('verification', 'test@alpha.test', 'one-time-secret')])

    def test_concurrent_employee_creates_respect_single_seat(self):
        with session(self.db) as connection:
            connection.execute("UPDATE subscription_plans SET max_employees=1 "
                               "WHERE code='starter-trial'")
        with self.app(enforce_subscriptions=True) as client:
            headers = self.owner(client)

            def create(index):
                return client.post('/api/v1/employees', headers=headers, json={
                    'employee_code': f'SEAT-{index:03d}',
                    'full_name': f'Test Employee {index}',
                    'job_title': 'Developer', 'department': 'Engineering',
                    'hire_date': '2025-01-01',
                }).status_code

            with ThreadPoolExecutor(max_workers=4) as pool:
                codes = list(pool.map(create, range(4)))
            self.assertEqual(codes.count(201), 1, codes)
            self.assertEqual(codes.count(409), 3, codes)


if __name__ == '__main__':
    unittest.main()
