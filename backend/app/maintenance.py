"""Explicit retention cleanup for expired authentication and email secrets.

Run on a trusted backend machine as a scheduled task, not within API requests.
Does not delete users, employees, subscriptions or audit records.
"""

import argparse
import os
import time

from .database import session


DEFAULT_RETENTION_SECONDS = 7 * 24 * 3600


def purge_expired(connection, *, now: int | None = None,
                  retention_seconds: int = DEFAULT_RETENTION_SECONDS) -> dict:
    if retention_seconds < 0:
        raise ValueError('Retention period cannot be negative')
    cutoff = (int(time.time()) if now is None else now) - retention_seconds
    counts = {}
    targets = [
        ('rate_limit_hits', 'expires_at'),
        ('password_resets', 'expires_at'),
        ('email_verifications', 'expires_at'),
        ('user_invitations', 'expires_at'),
    ]
    for table, column in targets:
        counts[table] = connection.execute(
            f'DELETE FROM {table} WHERE {column}<?', (cutoff,),
        ).rowcount
    counts['consumed_refresh_tokens'] = connection.execute(
        'DELETE FROM consumed_refresh_tokens WHERE session_id IN '
        '(SELECT id FROM user_sessions WHERE expires_at<?)', (cutoff,),
    ).rowcount
    counts['user_sessions'] = connection.execute(
        'DELETE FROM user_sessions WHERE expires_at<?', (cutoff,),
    ).rowcount
    counts['mail_outbox'] = connection.execute(
        "DELETE FROM mail_outbox WHERE (status='sent' AND sent_at<?) OR "
        "(status='dead' AND created_at<?)", (cutoff, cutoff),
    ).rowcount
    return counts


def main():
    parser = argparse.ArgumentParser(description='Purge expired HRM auth/mail metadata')
    parser.add_argument('--confirm', action='store_true',
                        help='Required because this deletes expired records')
    args = parser.parse_args()
    if not args.confirm:
        parser.error('Provide --confirm after reviewing the retention policy')
    path = os.getenv('HRM_DATABASE_URL') or os.getenv('HRM_DB_PATH',
                                                      './data/hrm_dev.sqlite3')
    with session(path) as connection:
        counts = purge_expired(connection)
    print('Expired metadata removed:', counts)


if __name__ == '__main__':
    main()
