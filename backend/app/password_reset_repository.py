"""Organization-scoped, hashed, single-use password recovery tokens."""

import json
import time
from uuid import uuid4

from .session_repository import token_hash


RESET_TTL_SECONDS = 30 * 60
RESET_COOLDOWN_SECONDS = 60


class PasswordResetRepository:
    def __init__(self, connection):
        self.connection = connection

    def request(self, *, organization_code: str, email: str, raw_token: str):
        row = self.connection.execute(
            'SELECT u.id,u.organization_id FROM users u '
            'JOIN organizations o ON o.id=u.organization_id '
            "WHERE o.code=? AND u.email=? AND u.is_active=TRUE AND o.status='active'",
            (organization_code, email),
        ).fetchone()
        if row is None:
            return False
        now = int(time.time())
        last = self.connection.execute(
            'SELECT MAX(created_at) FROM password_resets WHERE user_id=?',
            (row['id'],),
        ).fetchone()[0]
        if last is not None and now - last < RESET_COOLDOWN_SECONDS:
            return False
        self.connection.execute(
            'UPDATE password_resets SET consumed_at=? '
            'WHERE user_id=? AND consumed_at IS NULL',
            (now, row['id']),
        )
        self.connection.execute(
            'INSERT INTO password_resets '
            '(token_hash,organization_id,user_id,created_at,expires_at) '
            'VALUES (?,?,?,?,?)',
            (token_hash(raw_token), row['organization_id'], row['id'],
             now, now + RESET_TTL_SECONDS),
        )
        return True

    def confirm(self, *, raw_token: str, password_hash: str) -> bool:
        now = int(time.time())
        digest = token_hash(raw_token)
        row = self.connection.execute(
            'SELECT r.user_id,r.organization_id FROM password_resets r '
            'JOIN users u ON u.id=r.user_id '
            'JOIN organizations o ON o.id=r.organization_id '
            'WHERE r.token_hash=? AND r.consumed_at IS NULL AND r.expires_at>? '
            "AND u.is_active=TRUE AND o.status='active'",
            (digest, now),
        ).fetchone()
        if row is None:
            return False
        changed = self.connection.execute(
            'UPDATE password_resets SET consumed_at=? '
            'WHERE token_hash=? AND consumed_at IS NULL AND expires_at>?',
            (now, digest, now),
        ).rowcount
        if changed != 1:
            return False
        self.connection.execute(
            'UPDATE users SET password_hash=? WHERE id=? AND organization_id=?',
            (password_hash, row['user_id'], row['organization_id']),
        )
        self.connection.execute(
            'UPDATE user_sessions SET revoked_at=? '
            'WHERE user_id=? AND revoked_at IS NULL',
            (now, row['user_id']),
        )
        self.connection.execute(
            'INSERT INTO audit_events(id,organization_id,actor_id,action,'
            "entity_type,entity_id,changed_fields) VALUES (?,?,?,'reset_password','user',?,?)",
            (str(uuid4()), row['organization_id'], row['user_id'],
             row['user_id'], json.dumps(['credentials'])),
        )
        return True
