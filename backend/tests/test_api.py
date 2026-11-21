"""Integration tests for auth, tenant isolation, RBAC and employee lifecycle."""

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import unittest

from fastapi.testclient import TestClient

from app.bootstrap import create_organization_owner
from app.database import session
from app.main import create_app
from app.security import hash_password


TEST_SECRET = "only-for-tests-do-not-use-in-production-12345"
EMPLOYEE = {
    "employee_code": "EMP-042",
    "full_name": "Example Employee",
    "job_title": "Software Developer",
    "department": "Engineering",
    "email": "employee@example.com",
    "hire_date": "2024-05-01",
}


class EmployeesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "hrm.db")
        self.alpha_id, self.owner_id = create_organization_owner(
            self.db_path, code="alpha", name="Alpha Team",
            email="owner@example.com", password="demo-password-for-tests-123",
        )
        self.beta_id, _ = create_organization_owner(
            self.db_path, code="beta", name="Beta Team",
            email="owner@example.com", password="demo-password-for-tests-123",
        )
        with session(self.db_path) as connection:
            connection.execute(
                "INSERT INTO users (id,organization_id,email,password_hash,role) "
                "VALUES (?,?,?,?,?)",
                (str(uuid4()), self.alpha_id, "viewer@example.com",
                 hash_password("viewer-password-for-tests-123"), "viewer"),
            )
        self.client = TestClient(create_app(database_path=self.db_path, jwt_secret=TEST_SECRET))
        self.client.__enter__()
        self.alpha = self.login("alpha", "owner@example.com", "demo-password-for-tests-123")
        self.beta = self.login("beta", "owner@example.com", "demo-password-for-tests-123")
        self.viewer = self.login("alpha", "viewer@example.com", "viewer-password-for-tests-123")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self, org, email, password):
        response = self.client.post("/api/v1/auth/token", json={
            "organization_code": org, "email": email, "password": password,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def create_employee(self):
        response = self.client.post("/api/v1/employees", json=EMPLOYEE, headers=self.alpha)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_authentication_required_and_invalid_credentials(self):
        self.assertEqual(self.client.get("/api/v1/employees").status_code, 401)
        bad = self.client.post("/api/v1/auth/token", json={
            "organization_code": "alpha", "email": "owner@example.com",
            "password": "invalid",
        })
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.alpha).json()["role"], "owner")

    def test_crud_search_and_audit(self):
        employee = self.create_employee()
        employee_id = employee["id"]
        self.assertEqual(employee["version"], 1)
        self.assertEqual(self.client.post(
            "/api/v1/employees", json=EMPLOYEE, headers=self.alpha,
        ).status_code, 409)
        listing = self.client.get("/api/v1/employees?search=Example&limit=1", headers=self.alpha)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)
        edit = self.client.patch(f"/api/v1/employees/{employee_id}",
            json={"expected_version": 1, "job_title": "Senior Developer"}, headers=self.alpha)
        self.assertEqual(edit.status_code, 200, edit.text)
        self.assertEqual(edit.json()["version"], 2)
        self.assertEqual(edit.json()["job_title"], "Senior Developer")
        self.assertEqual(self.client.patch(f"/api/v1/employees/{employee_id}",
            json={"expected_version": 1, "department": "IT"}, headers=self.alpha).status_code, 409)
        self.assertEqual(self.client.delete(
            f"/api/v1/employees/{employee_id}?expected_version=2", headers=self.alpha,
        ).status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/employees/{employee_id}", headers=self.alpha).status_code, 404)
        with session(self.db_path) as connection:
            events = connection.execute("SELECT action, changed_fields FROM audit_events ORDER BY rowid").fetchall()
        self.assertEqual([event["action"] for event in events], ["create", "update", "archive"])
        self.assertEqual(json.loads(events[1]["changed_fields"]), ["job_title"])

    def test_cross_organization_isolation(self):
        employee = self.create_employee()
        path = f"/api/v1/employees/{employee['id']}"
        self.assertEqual(self.client.get(path, headers=self.beta).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/employees", headers=self.beta).json()["total"], 0)
        self.assertEqual(self.client.patch(path, headers=self.beta,
            json={"expected_version": 1, "job_title": "Different"}).status_code, 404)
        self.assertEqual(self.client.delete(path + "?expected_version=1", headers=self.beta).status_code, 404)

    def test_viewer_can_read_but_cannot_write(self):
        employee = self.create_employee()
        path = f"/api/v1/employees/{employee['id']}"
        self.assertEqual(self.client.get(path, headers=self.viewer).status_code, 200)
        self.assertEqual(self.client.post(
            "/api/v1/employees", json=EMPLOYEE, headers=self.viewer,
        ).status_code, 403)
        self.assertEqual(self.client.patch(path, headers=self.viewer,
            json={"expected_version": 1, "job_title": "Different"}).status_code, 403)
        self.assertEqual(self.client.delete(path + "?expected_version=1", headers=self.viewer).status_code, 403)

    def test_input_validation_and_unmodifiable_fields(self):
        invalid = dict(EMPLOYEE, employee_code="invalid code with spaces")
        self.assertEqual(self.client.post("/api/v1/employees", json=invalid, headers=self.alpha).status_code, 422)
        employee = self.create_employee()
        path = f"/api/v1/employees/{employee['id']}"
        self.assertEqual(self.client.patch(path, headers=self.alpha,
            json={"expected_version": 1, "organization_id": self.beta_id}).status_code, 422)
        self.assertEqual(self.client.patch(path, headers=self.alpha,
            json={"expected_version": 1, "full_name": None}).status_code, 422)

    def test_permissions_checked_against_current_account_state(self):
        employee = self.create_employee()
        with session(self.db_path) as connection:
            connection.execute(
                "UPDATE users SET is_active=0 WHERE id=?", (self.owner_id,),
            )
        self.assertEqual(self.client.get(
            f"/api/v1/employees/{employee['id']}", headers=self.alpha,
        ).status_code, 401)

    def test_unknown_organization_does_not_issue_token(self):
        result = self.client.post("/api/v1/auth/token", json={
            "organization_code": "unknown", "email": "owner@example.com",
            "password": "demo-password-for-tests-123",
        })
        self.assertEqual(result.status_code, 401)


if __name__ == "__main__":
    unittest.main()
