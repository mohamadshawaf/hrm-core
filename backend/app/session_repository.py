"""Revocable per-device sessions with one-time rotating refresh tokens."""

import hashlib
import time
from uuid import uuid4


REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class UserSessionRepository:
    def __init__(self, connection):
        self.connection = connection

    def create(self, *, organization_id: str, user_id: str,
               raw_refresh_token: str, device_label: str) -> str:
        session_id = str(uuid4())
        now = int(time.time())
        self.connection.execute(
            'INSERT INTO user_sessions(id,organization_id,user_id,refresh_token_hash,'
            'device_label,created_at,expires_at) VALUES (?,?,?,?,?,?,?)',
            (session_id, organization_id, user_id, token_hash(raw_refresh_token),
             device_label, now, now + REFRESH_TTL_SECONDS),
        )
        return session_id

    def active(self, *, user_id: str, session_id: str) -> bool:
        row = self.connection.execute(
            'SELECT id FROM user_sessions WHERE id=? AND user_id=? '
            'AND revoked_at IS NULL AND expires_at>?',
            (session_id, user_id, int(time.time())),
        ).fetchone()
        return row is not None

    def rotate(self, presented_token: str, new_token: str):
        now = int(time.time())
        old_digest = token_hash(presented_token)
        row = self.connection.execute(
            'SELECT s.id,s.user_id,s.organization_id,s.expires_at,s.revoked_at '
            'FROM user_sessions s JOIN users u ON u.id=s.user_id '
            'JOIN organizations o ON o.id=s.organization_id '
            'WHERE s.refresh_token_hash=? AND u.is_active=TRUE '
            "AND o.status='active'",
            (old_digest,),
        ).fetchone()
        if row is None:
            replay = self.connection.execute(
                'SELECT session_id FROM consumed_refresh_tokens WHERE token_hash=?',
                (old_digest,),
            ).fetchone()
            if replay is not None:
                self.connection.execute(
                    'UPDATE user_sessions SET revoked_at=? WHERE id=? AND revoked_at IS NULL',
                    (now, replay['session_id']),
                )
            return None
        if row['revoked_at'] is not None or row['expires_at'] <= now:
            return None
        updated = self.connection.execute(
            'UPDATE user_sessions SET refresh_token_hash=? WHERE id=? '
            'AND refresh_token_hash=? AND revoked_at IS NULL AND expires_at>?',
            (token_hash(new_token), row['id'], old_digest, now),
        ).rowcount
        if updated != 1:
            return None
        self.connection.execute(
            'INSERT INTO consumed_refresh_tokens(token_hash,session_id,consumed_at) '
            'VALUES (?,?,?)',
            (old_digest, row['id'], now),
        )
        return {'session_id': row['id'], 'user_id': row['user_id'],
                'organization_id': row['organization_id'],
                'expires_at': row['expires_at']}

    def list_for_user(self, user_id: str, current_session: str):
        rows = self.connection.execute(
            'SELECT id,device_label,created_at,expires_at,revoked_at '
            'FROM user_sessions WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 100',
            (user_id,),
        ).fetchall()
        return [{**dict(row),
                 'is_current': row['id'] == current_session,
                 'is_active': row['revoked_at'] is None and
                              row['expires_at'] > int(time.time())}
                for row in rows]

    def revoke(self, user_id: str, session_id: str) -> bool:
        row = self.connection.execute(
            'SELECT id FROM user_sessions WHERE user_id=? AND id=?',
            (user_id, session_id),
        ).fetchone()
        if row is None:
            return False
        self.connection.execute(
            'UPDATE user_sessions SET revoked_at=? '
            'WHERE user_id=? AND id=? AND revoked_at IS NULL',
            (int(time.time()), user_id, session_id),
        )
        return True

    def revoke_all(self, user_id: str):
        self.connection.execute(
            'UPDATE user_sessions SET revoked_at=? '
            'WHERE user_id=? AND revoked_at IS NULL',
            (int(time.time()), user_id),
        )
