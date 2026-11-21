"""Encrypted transactional email outbox with retryable delivery leases.

Queueing a verification code happens in the same DB transaction as saving
the token digest. The worker sends after commit; at-least-once delivery is
possible if a worker crashes immediately after the SMTP send succeeds.
"""

import json
import os
import time
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAIL_KINDS = frozenset(('verification', 'invitation', 'reset'))
MAX_ATTEMPTS = 5
LEASE_SECONDS = 90


def parse_mail_key(hex_key: str) -> bytes:
    try:
        key = bytes.fromhex(hex_key)
    except ValueError:
        raise RuntimeError('HRM_MAIL_OUTBOX_KEY must contain 64 hex characters') from None
    if len(key) != 32:
        raise RuntimeError('HRM_MAIL_OUTBOX_KEY must be exactly 32 bytes (64 hex characters)')
    return key


class MailQueue:
    def __init__(self, connection, key: bytes):
        self.connection = connection
        if len(key) != 32:
            raise ValueError('Mail queue requires an AES-256 key')
        self.key = key

    @staticmethod
    def _associated_data(id_: str, kind: str, recipient: str) -> bytes:
        return f'hrm-mail\0{id_}\0{kind}\0{recipient}'.encode('utf-8')

    def enqueue(self, *, kind: str, recipient: str,
                organization_code: str, token: str) -> str:
        if kind not in MAIL_KINDS:
            raise ValueError('Unsupported mail kind')
        id_ = str(uuid4())
        nonce = os.urandom(12)
        data = json.dumps({'organization_code': organization_code, 'token': token},
                          separators=(',', ':')).encode('utf-8')
        ciphertext = AESGCM(self.key).encrypt(
            nonce, data, self._associated_data(id_, kind, recipient),
        )
        now = int(time.time())
        self.connection.execute(
            'INSERT INTO mail_outbox(id,kind,recipient_email,nonce,ciphertext,'
            'next_attempt_at,created_at) VALUES (?,?,?,?,?,?,?)',
            (id_, kind, recipient, nonce, ciphertext, now, now),
        )
        return id_

    def claim(self, *, now: int | None = None):
        timestamp = int(time.time()) if now is None else now
        row = self.connection.execute(
            'SELECT id,kind,recipient_email,nonce,ciphertext,attempts '
            'FROM mail_outbox WHERE next_attempt_at<=? '
            "AND (status='pending' OR (status='processing' AND lease_until<=?)) "
            'ORDER BY created_at,id LIMIT 1',
            (timestamp, timestamp),
        ).fetchone()
        if row is None:
            return None
        updated = self.connection.execute(
            "UPDATE mail_outbox SET status='processing',attempts=attempts+1,"
            'lease_until=? WHERE id=? AND next_attempt_at<=? AND '
            "(status='pending' OR (status='processing' AND lease_until<=?))",
            (timestamp + LEASE_SECONDS, row['id'], timestamp, timestamp),
        ).rowcount
        if updated != 1:
            return None
        return {**dict(row), 'attempts': row['attempts'] + 1}

    @classmethod
    def decrypt_message(cls, row: dict, key: bytes):
        raw = AESGCM(key).decrypt(
            bytes(row['nonce']), bytes(row['ciphertext']),
            cls._associated_data(row['id'], row['kind'], row['recipient_email']),
        )
        return json.loads(raw.decode('utf-8'))

    def sent(self, id_: str, *, now: int | None = None):
        timestamp = int(time.time()) if now is None else now
        self.connection.execute(
            "UPDATE mail_outbox SET status='sent',nonce=NULL,ciphertext=NULL,"
            'sent_at=?,lease_until=NULL WHERE id=? AND status=?',
            (timestamp, id_, 'processing'),
        )

    def failed(self, id_: str, attempts: int, *, now: int | None = None):
        timestamp = int(time.time()) if now is None else now
        status = 'dead' if attempts >= MAX_ATTEMPTS else 'pending'
        delay = min(3600, 60 * 2 ** max(0, attempts - 1))
        self.connection.execute(
            'UPDATE mail_outbox SET status=?,next_attempt_at=?,lease_until=NULL '
            'WHERE id=? AND status=?',
            (status, timestamp + delay, id_, 'processing'),
        )
