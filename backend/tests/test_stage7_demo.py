"""Milestone 7 fictional portfolio/demo regression tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from app.database import session
from app.demo_seed import create_demo_database
from app.main import create_app


class StageSevenDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'portfolio-demo.sqlite3')

    def tearDown(self):
        self.temp.cleanup()

    def test_populates_fabricated_tenants_with_separate_employees(self):
        self.assertEqual(create_demo_database(self.db, password='local-demo-password-2026'),
                         {'atlas-demo': 8, 'cedar-demo': 12})
        with session(self.db) as conn:
            rows = conn.execute('SELECT o.code, COUNT(e.id) AS total FROM organizations o '
                'LEFT JOIN employees e ON o.id=e.organization_id '
                'GROUP BY o.id ORDER BY o.code').fetchall()
            self.assertEqual([(r['code'], r['total']) for r in rows],
                             [('atlas-demo', 8), ('cedar-demo', 12)])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0], 20)
            self.assertTrue(all(r['email'].endswith('@example.invalid') for r in
                conn.execute('SELECT email FROM employees')))

    def test_seeded_accounts_enforce_tenant_isolation_via_api(self):
        create_demo_database(self.db, password='local-demo-password-2026')
        with TestClient(create_app(database_path=self.db,
            jwt_secret='stage7-secret-for-disposable-test-only')) as client:
            sessions = {}
            for code in ('atlas-demo', 'cedar-demo'):
                token = client.post('/api/v1/auth/token', json={
                    'organization_code': code,
                    'email': f'owner@{code.split("-")[0]}.example.invalid',
                    'password': 'local-demo-password-2026',
                })
                self.assertEqual(token.status_code, 200, token.text)
                headers = {'Authorization': 'Bearer ' + token.json()['access_token']}
                sessions[code] = headers
                found = client.get('/api/v1/employees', headers=headers)
                self.assertEqual(found.status_code, 200, found.text)
                self.assertEqual(found.json()['total'], 8 if code == 'atlas-demo' else 12)
                self.assertTrue(all(item['employee_code'].startswith(
                    'D1-' if code == 'atlas-demo' else 'D2-')
                    for item in found.json()['items']))

    def test_refuses_existing_file_or_production_environment(self):
        create_demo_database(self.db, password='local-demo-password-2026')
        with self.assertRaises(FileExistsError):
            create_demo_database(self.db, password='local-demo-password-2026')
        with patch.dict('os.environ', {'HRM_ENV': 'production'}):
            with self.assertRaisesRegex(ValueError, 'production'):
                create_demo_database(str(Path(self.temp.name) / 'new.db'),
                                     password='local-demo-password-2026')
        with self.assertRaisesRegex(ValueError, 'SQLite'):
            create_demo_database('postgresql://ignored/test',
                                 password='local-demo-password-2026')


if __name__ == '__main__':
    unittest.main()
