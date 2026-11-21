"""Database-backed fixed-window throttling; no plaintext IP or email keys.

The caller must commit the write independently of a later failed request;
otherwise invalid passwords would undo their own login-attempt counters.
"""

import hashlib
import hmac
import time


class RateLimiter:
    def __init__(self, connection, secret: str):
        self.connection = connection
        self.secret = secret.encode('utf-8')

    def hit(self, category: str, subject: str, *, limit: int,
            window_seconds: int, now: int | None = None) -> bool:
        if limit < 1 or window_seconds < 1:
            raise ValueError('Rate-limit threshold must be positive')
        timestamp = int(time.time()) if now is None else now
        start = timestamp - timestamp % window_seconds
        digest = hmac.new(
            self.secret, f'{category}\0{subject}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        self.connection.execute(
            'INSERT INTO rate_limit_hits(bucket_key,window_start,attempts,expires_at) '
            'VALUES (?,?,1,?) ON CONFLICT(bucket_key,window_start) '
            'DO UPDATE SET attempts=attempts+1',
            (digest, start, start + window_seconds),
        )
        row = self.connection.execute(
            'SELECT attempts FROM rate_limit_hits WHERE bucket_key=? '
            'AND window_start=?', (digest, start),
        ).fetchone()
        return row['attempts'] <= limit
