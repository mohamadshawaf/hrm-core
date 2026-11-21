"""Database access isolated from HTTP transport and authentication responses.

All queries are organization-scoped and parameterized. The caller owns the
connection/transaction to keep writes and audit events atomic.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
import time
from uuid import uuid4

from .database import STARTER_PLAN_ID, TRIAL_DURATION_SECONDS


class AccountRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def active_user(self, user_id: str):
        return self.connection.execute(
            "SELECT u.id, u.organization_id, u.role FROM users u "
            "JOIN organizations o ON o.id=u.organization_id "
            "WHERE u.id=? AND u.is_active=TRUE AND o.status='active'",
            (user_id,),
        ).fetchone()

    def login_account(self, organization_code: str, email: str):
        return self.connection.execute(
            "SELECT u.id, u.organization_id, u.password_hash FROM users u "
            "JOIN organizations o ON o.id=u.organization_id "
            "WHERE o.code=? AND u.email=? AND u.is_active=TRUE AND o.status='active'",
            (organization_code, email),
        ).fetchone()


class OrganizationRegistrationRepository:
    """Self-service onboarding without exposing access to pending tenants."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def register(self, *, code: str, name: str, email: str,
                 password_hash: str, token_hash: str, issued_at: int, expires_at: int) -> None:
        org_id, owner_id = str(uuid4()), str(uuid4())
        self.connection.execute(
            "INSERT INTO organizations(id, code, name, status) "
            "VALUES (?, ?, ?, 'pending_email')",
            (org_id, code, name),
        )
        self.connection.execute(
            "INSERT INTO users(id, organization_id, email, password_hash, role) "
            "VALUES (?, ?, ?, ?, 'owner')",
            (owner_id, org_id, email, password_hash),
        )
        self.connection.execute(
            "INSERT INTO email_verifications(token_hash, organization_id, owner_id, issued_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (token_hash, org_id, owner_id, issued_at, expires_at),
        )
        self.connection.execute(
            "INSERT INTO organization_subscriptions "
            "(organization_id,plan_id,status,period_ends_at) "
            "VALUES (?, ?, 'trialing', ?)",
            (org_id, STARTER_PLAN_ID, issued_at + TRIAL_DURATION_SECONDS),
        )

    def resend(self, *, code: str, email: str, token_hash: str,
               issued_at: int, expires_at: int) -> bool:
        row = self.connection.execute(
            "SELECT o.id AS org_id, u.id AS owner_id, "
            "(SELECT MAX(v.issued_at) FROM email_verifications v "
            "WHERE v.organization_id=o.id) AS last_sent_at "
            "FROM organizations o JOIN users u ON u.organization_id=o.id "
            "WHERE o.code=? AND o.status='pending_email' AND u.email=? "
            "AND u.role='owner' AND u.is_active=TRUE",
            (code, email),
        ).fetchone()
        if row is None or (row['last_sent_at'] is not None and
                           issued_at - row['last_sent_at'] < 60):
            return False
        self.connection.execute(
            "UPDATE email_verifications SET consumed_at=? "
            "WHERE organization_id=? AND consumed_at IS NULL",
            (issued_at, row['org_id']),
        )
        self.connection.execute(
            "INSERT INTO email_verifications(token_hash, organization_id, owner_id, issued_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (token_hash, row['org_id'], row['owner_id'], issued_at, expires_at),
        )
        return True

    def activate(self, token: str, now: int | None = None) -> bool:
        time_now = int(time.time()) if now is None else now
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        row = self.connection.execute(
            "SELECT v.organization_id FROM email_verifications v "
            "JOIN organizations o ON o.id=v.organization_id "
            "WHERE v.token_hash=? AND v.consumed_at IS NULL "
            "AND v.expires_at>? AND o.status='pending_email'",
            (digest, time_now),
        ).fetchone()
        if row is None:
            return False
        changed = self.connection.execute(
            "UPDATE email_verifications SET consumed_at=? "
            "WHERE token_hash=? AND consumed_at IS NULL AND expires_at>?",
            (time_now, digest, time_now),
        ).rowcount
        if changed != 1:
            return False
        activated = self.connection.execute(
            "UPDATE organizations SET status='active' "
            "WHERE id=? AND status='pending_email'",
            (row['organization_id'],),
        ).rowcount
        if activated != 1:
            raise RuntimeError('Organization activation transaction failed')
        return True


class EmployeeRepository:
    _UPDATABLE_FIELDS = frozenset({
        "full_name", "job_title", "department", "email", "phone",
        "hire_date", "status",
    })

    def __init__(self, connection: sqlite3.Connection, organization_id: str, actor_id: str):
        self.connection = connection
        self.organization_id = organization_id
        self.actor_id = actor_id

    def get(self, employee_id: str):
        return self.connection.execute(
            "SELECT * FROM employees WHERE id=? AND organization_id=? AND archived_at IS NULL",
            (employee_id, self.organization_id),
        ).fetchone()

    def list(self, search: str, limit: int, offset: int):
        condition = "organization_id=? AND archived_at IS NULL"
        params = [self.organization_id]
        if search.strip():
            condition += " AND (instr(lower(full_name), lower(?))>0 OR instr(lower(employee_code), lower(?))>0)"
            params.extend([search.strip(), search.strip()])
        total = self.connection.execute(
            f"SELECT COUNT(*) FROM employees WHERE {condition}", params,
        ).fetchone()[0]
        rows = self.connection.execute(
            f"SELECT * FROM employees WHERE {condition} "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return total, rows

    def create(self, payload: dict) -> str:
        employee_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO employees(id, organization_id, employee_code, full_name, "
            "job_title, department, email, phone, hire_date, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (employee_id, self.organization_id, payload["employee_code"],
             payload["full_name"], payload["job_title"], payload["department"],
             payload["email"], payload["phone"], payload["hire_date"], payload["status"]),
        )
        self._audit(employee_id, "create", list(payload))
        return employee_id

    def update(self, employee_id: str, fields: dict, expected_version: int) -> bool:
        if not fields or not set(fields).issubset(self._UPDATABLE_FIELDS):
            raise ValueError("Unsupported employee update field")
        columns = ", ".join(f"{field}=?" for field in fields)
        updated = self.connection.execute(
            f"UPDATE employees SET {columns}, version=version+1, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND organization_id=? "
            "AND archived_at IS NULL AND version=?",
            [*fields.values(), employee_id, self.organization_id, expected_version],
        ).rowcount
        if updated == 1:
            self._audit(employee_id, "update", list(fields))
        return updated == 1

    def archive(self, employee_id: str, expected_version: int) -> bool:
        changed = self.connection.execute(
            "UPDATE employees SET archived_at=CURRENT_TIMESTAMP, "
            "updated_at=CURRENT_TIMESTAMP, version=version+1 "
            "WHERE id=? AND organization_id=? AND archived_at IS NULL AND version=?",
            (employee_id, self.organization_id, expected_version),
        ).rowcount
        if changed == 1:
            self._audit(employee_id, "archive", ["archived_at"])
        return changed == 1

    def _audit(self, employee_id: str, action: str, fields: list[str]) -> None:
        self.connection.execute(
            "INSERT INTO audit_events(id, organization_id, actor_id, action, "
            "entity_type, entity_id, changed_fields) VALUES (?, ?, ?, ?, 'employee', ?, ?)",
            (str(uuid4()), self.organization_id, self.actor_id, action,
             employee_id, json.dumps(sorted(fields))),
        )
