"""Single-use, organization-scoped, email-delivered account invitations."""

import json
import time
from uuid import uuid4

from .session_repository import token_hash


INVITE_TTL_SECONDS = 48 * 60 * 60
INVITE_COOLDOWN_SECONDS = 60


class InvitationRepository:
    def __init__(self, connection):
        self.connection = connection

    def invite(self, *, organization_id: str, owner_id: str,
               email: str, role: str, raw_token: str):
        if role not in ('hr', 'viewer'):
            raise ValueError('Invitations cannot grant owner or platform permissions')
        existing = self.connection.execute(
            'SELECT id FROM users WHERE organization_id=? AND email=?',
            (organization_id, email),
        ).fetchone()
        if existing is not None:
            return 'existing'
        now = int(time.time())
        last = self.connection.execute(
            'SELECT MAX(created_at) FROM user_invitations '
            'WHERE organization_id=? AND email=?',
            (organization_id, email),
        ).fetchone()[0]
        if last is not None and now - last < INVITE_COOLDOWN_SECONDS:
            return 'cooldown'
        self.connection.execute(
            'UPDATE user_invitations SET revoked_at=? WHERE organization_id=? '
            'AND email=? AND accepted_at IS NULL AND revoked_at IS NULL',
            (now, organization_id, email),
        )
        self.connection.execute(
            'INSERT INTO user_invitations '
            '(token_hash,organization_id,email,role,invited_by,created_at,expires_at) '
            'VALUES (?,?,?,?,?,?,?)',
            (token_hash(raw_token), organization_id, email, role, owner_id,
             now, now + INVITE_TTL_SECONDS),
        )
        return 'created'

    def list_for_company(self, organization_id: str):
        rows = self.connection.execute(
            'SELECT email,role,created_at,expires_at,accepted_at,revoked_at '
            'FROM user_invitations WHERE organization_id=? '
            'ORDER BY created_at DESC LIMIT 100',
            (organization_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def accept(self, raw_token: str, password_hash: str):
        digest = token_hash(raw_token)
        now = int(time.time())
        invite = self.connection.execute(
            'SELECT i.organization_id,i.email,i.role,i.invited_by '
            'FROM user_invitations i '
            'JOIN organizations o ON o.id=i.organization_id '
            "WHERE i.token_hash=? AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
            "AND i.expires_at>? AND o.status='active'",
            (digest, now),
        ).fetchone()
        if invite is None:
            return None
        existing = self.connection.execute(
            'SELECT id FROM users WHERE organization_id=? AND email=?',
            (invite['organization_id'], invite['email']),
        ).fetchone()
        if existing is not None:
            return None
        account_id = str(uuid4())
        self.connection.execute(
            'INSERT INTO users(id,organization_id,email,password_hash,role) '
            'VALUES (?,?,?,?,?)',
            (account_id, invite['organization_id'], invite['email'],
             password_hash, invite['role']),
        )
        self.connection.execute(
            'UPDATE user_invitations SET accepted_at=? '
            'WHERE token_hash=? AND accepted_at IS NULL AND revoked_at IS NULL',
            (now, digest),
        )
        self.connection.execute(
            'INSERT INTO audit_events(id,organization_id,actor_id,action,'
            "entity_type,entity_id,changed_fields) VALUES (?,?,?,'accept_invitation','user',?,?)",
            (str(uuid4()), invite['organization_id'], invite['invited_by'],
             account_id, json.dumps(['email', 'role'])),
        )
        return {'id': account_id, 'organization_id': invite['organization_id'],
                'email': invite['email'], 'role': invite['role']}
