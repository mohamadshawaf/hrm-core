"""Tenant-scoped user provisioning; platform roles cannot be granted here."""

from __future__ import annotations

import json
import sqlite3
from uuid import uuid4


class OrganizationUserRepository:
    def __init__(self, connection: sqlite3.Connection,
                 organization_id: str, actor_id: str):
        self.connection = connection
        self.organization_id = organization_id
        self.actor_id = actor_id

    def list(self, limit: int, offset: int) -> dict:
        total = self.connection.execute(
            'SELECT COUNT(*) FROM users WHERE organization_id=?',
            (self.organization_id,),
        ).fetchone()[0]
        rows = self.connection.execute(
            'SELECT id,email,role,is_active,version,created_at FROM users '
            'WHERE organization_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
            (self.organization_id, limit, offset),
        ).fetchall()
        return {'items': [dict(row) for row in rows], 'total': total,
                'limit': limit, 'offset': offset}

    def get(self, user_id: str):
        return self.connection.execute(
            'SELECT id,email,role,is_active,version,created_at FROM users '
            'WHERE id=? AND organization_id=?',
            (user_id, self.organization_id),
        ).fetchone()

    def create(self, *, email: str, password_hash: str, role: str):
        if role not in {'hr', 'viewer'}:
            raise ValueError('Only scoped HR/viewer accounts are provisionable')
        user_id = str(uuid4())
        self.connection.execute(
            'INSERT INTO users(id,organization_id,email,password_hash,role) '
            'VALUES (?,?,?,?,?)',
            (user_id, self.organization_id, email, password_hash, role),
        )
        self._audit('create', user_id, ['email', 'role', 'is_active'])
        return self.get(user_id)

    def patch(self, user_id: str, fields: dict, expected_version: int) -> str:
        if not fields or not set(fields).issubset({'role', 'is_active'}):
            raise ValueError('Unsupported update fields')
        target = self.get(user_id)
        if target is None:
            return 'not_found'
        if target['role'] == 'owner':
            return 'protected_owner'
        if 'role' in fields and fields['role'] not in {'hr', 'viewer'}:
            raise ValueError('Invalid role')
        updates = ', '.join(f'{key}=?' for key in fields)
        changed = self.connection.execute(
            f'UPDATE users SET {updates},version=version+1 '
            "WHERE id=? AND organization_id=? AND role!='owner' AND version=?",
            (*fields.values(), user_id, self.organization_id, expected_version),
        ).rowcount
        if changed == 0:
            return 'conflict'
        self._audit('update', user_id, list(fields))
        return 'updated'

    def _audit(self, action: str, target_id: str, fields: list[str]):
        self.connection.execute(
            'INSERT INTO audit_events(id,organization_id,actor_id,action, '
            "entity_type,entity_id,changed_fields) VALUES (?,?,?,?,'user',?,?)",
            (str(uuid4()), self.organization_id, self.actor_id, action,
             target_id, json.dumps(sorted(fields))),
        )
