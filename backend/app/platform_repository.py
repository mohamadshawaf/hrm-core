"""Privileged platform administration; isolated from organization user roles."""

import json
import sqlite3
from uuid import uuid4


class PlatformRepository:
    def __init__(self, connection: sqlite3.Connection, actor_id: str | None = None):
        self.connection = connection
        self.actor_id = actor_id

    def login_account(self, email: str):
        return self.connection.execute(
            'SELECT id,password_hash FROM platform_admins '
            'WHERE email=? AND role=? AND is_active=TRUE',
            (email, 'platform_owner'),
        ).fetchone()

    def active_admin(self, admin_id: str):
        return self.connection.execute(
            'SELECT id,email,role FROM platform_admins '
            'WHERE id=? AND is_active=TRUE AND role=?',
            (admin_id, 'platform_owner'),
        ).fetchone()

    def overview(self) -> dict:
        orgs = self.connection.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active, "
            "SUM(CASE WHEN status='pending_email' THEN 1 ELSE 0 END) AS pending, "
            "SUM(CASE WHEN status='suspended' THEN 1 ELSE 0 END) AS suspended "
            'FROM organizations'
        ).fetchone()
        employees = self.connection.execute(
            'SELECT COUNT(*) FROM employees WHERE archived_at IS NULL'
        ).fetchone()[0]
        return {
            'organizations_total': orgs['total'],
            'organizations_active': orgs['active'] or 0,
            'organizations_pending': orgs['pending'] or 0,
            'organizations_suspended': orgs['suspended'] or 0,
            'employees_total': employees,
        }

    def list_organizations(self, search: str, limit: int, offset: int) -> dict:
        condition = ''
        params: list = []
        if search.strip():
            condition = 'WHERE instr(lower(o.name),lower(?))>0 OR instr(lower(o.code),lower(?))>0'
            params = [search.strip(), search.strip()]
        total = self.connection.execute(
            f'SELECT COUNT(*) FROM organizations o {condition}', params,
        ).fetchone()[0]
        rows = self.connection.execute(
            'SELECT o.id,o.code,o.name,o.status,o.created_at, '
            's.plan_id,p.name AS plan_name,s.status AS subscription_status, '
            's.period_ends_at,s.version AS subscription_version, '
            '(SELECT COUNT(*) FROM employees e WHERE e.organization_id=o.id '
            'AND e.archived_at IS NULL) AS employees_count '
            'FROM organizations o '
            'LEFT JOIN organization_subscriptions s ON s.organization_id=o.id '
            'LEFT JOIN subscription_plans p ON p.id=s.plan_id '
            f'{condition} ORDER BY o.created_at DESC,o.id DESC LIMIT ? OFFSET ?',
            [*params, limit, offset],
        ).fetchall()
        return {'items': [dict(row) for row in rows], 'total': total,
                'limit': limit, 'offset': offset}

    def list_plans(self) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            'SELECT id,code,name,price_halalas,max_employees,is_active,created_at '
            'FROM subscription_plans ORDER BY created_at,id',
        ).fetchall()]

    def create_plan(self, *, code: str, name: str, price_halalas: int,
                    max_employees: int) -> dict:
        plan_id = str(uuid4())
        self.connection.execute(
            'INSERT INTO subscription_plans(id,code,name,price_halalas,max_employees) '
            'VALUES (?,?,?,?,?)',
            (plan_id, code, name, price_halalas, max_employees),
        )
        self._audit('create_plan', None, plan_id,
                    ['code', 'name', 'price_halalas', 'max_employees'])
        return dict(self.connection.execute(
            'SELECT id,code,name,price_halalas,max_employees,is_active,created_at '
            'FROM subscription_plans WHERE id=?', (plan_id,),
        ).fetchone())

    def change_organization_status(self, organization_id: str, status: str) -> str:
        row = self.connection.execute(
            'SELECT status FROM organizations WHERE id=?', (organization_id,),
        ).fetchone()
        if row is None:
            return 'missing'
        if row['status'] == 'pending_email':
            return 'pending_verification'
        if row['status'] == status:
            return 'unchanged'
        self.connection.execute(
            'UPDATE organizations SET status=? WHERE id=? AND status=?',
            (status, organization_id, row['status']),
        )
        self._audit('organization_status', organization_id, organization_id, ['status'])
        return 'updated'

    def change_subscription(self, *, organization_id: str, plan_id: str,
                            status: str, period_ends_at: int,
                            expected_version: int) -> str:
        organization = self.connection.execute(
            'SELECT id FROM organizations WHERE id=?', (organization_id,),
        ).fetchone()
        if organization is None:
            return 'missing_organization'
        plan = self.connection.execute(
            'SELECT is_active FROM subscription_plans WHERE id=?', (plan_id,),
        ).fetchone()
        if plan is None or not plan['is_active']:
            return 'invalid_plan'
        updated = self.connection.execute(
            'UPDATE organization_subscriptions SET plan_id=?,status=?, '
            'period_ends_at=?,version=version+1,updated_at=CURRENT_TIMESTAMP '
            'WHERE organization_id=? AND version=?',
            (plan_id, status, period_ends_at, organization_id, expected_version),
        ).rowcount
        if updated != 1:
            return 'conflict'
        self._audit('subscription_update', organization_id, organization_id,
                    ['plan_id', 'status', 'period_ends_at'])
        return 'updated'

    def _audit(self, action: str, organization_id: str | None,
               entity_id: str, fields: list[str]) -> None:
        if not self.actor_id:
            raise ValueError('A platform actor is required for mutations')
        self.connection.execute(
            'INSERT INTO platform_audit_events '
            '(id,actor_id,organization_id,action,entity_id,changed_fields) '
            'VALUES (?,?,?,?,?,?)',
            (str(uuid4()), self.actor_id, organization_id, action,
             entity_id, json.dumps(sorted(fields))),
        )
