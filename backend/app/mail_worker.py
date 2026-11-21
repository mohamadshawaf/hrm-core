"""Run as a separate local process or scheduled job; never inside HTTP calls."""

import argparse
import logging
import os

from .database import initialize, session
from .mail_queue import MailQueue, parse_mail_key
from .mailer import (configured_verification_sender, configured_invitation_sender,
                     configured_password_reset_sender)


def process_one(database_path: str, key: bytes, senders: dict) -> bool:
    with session(database_path) as connection:
        row = MailQueue(connection, key).claim()
    if row is None:
        return False
    try:
        # Decryption occurs only in worker memory. No secret is logged.
        payload = MailQueue.decrypt_message(row, key)
        if row['kind'] == 'verification':
            senders['verification'](row['recipient_email'], payload['token'])
        else:
            senders[row['kind']](row['recipient_email'],
                                 payload['organization_code'], payload['token'])
    except Exception:
        logging.getLogger('hrm.delivery').warning('Email delivery attempt failed')
        with session(database_path) as connection:
            MailQueue(connection, key).failed(row['id'], row['attempts'])
    else:
        with session(database_path) as connection:
            MailQueue(connection, key).sent(row['id'])
    return True


def process_batch(database_path: str, key: bytes, senders: dict, *, max_jobs: int = 50):
    completed = 0
    for _ in range(max_jobs):
        if not process_one(database_path, key, senders):
            break
        completed += 1
    return completed


def main():
    parser = argparse.ArgumentParser(description='Process HRM transactional email queue')
    parser.add_argument('--max-jobs', type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.max_jobs <= 500:
        parser.error('--max-jobs must be between 1 and 500')
    key_text = os.getenv('HRM_MAIL_OUTBOX_KEY', '')
    if not key_text:
        parser.error('HRM_MAIL_OUTBOX_KEY must be configured for queued delivery')
    key = parse_mail_key(key_text)
    path = (os.getenv('HRM_DATABASE_URL') or os.getenv('HRM_DB_PATH',
                                                       './data/hrm_dev.sqlite3'))
    initialize(path)
    senders = {
        'verification': configured_verification_sender(path),
        'invitation': configured_invitation_sender(path),
        'reset': configured_password_reset_sender(path),
    }
    count = process_batch(path, key, senders, max_jobs=args.max_jobs)
    print(f'Processed {count} queued email attempts')


if __name__ == '__main__':
    main()
