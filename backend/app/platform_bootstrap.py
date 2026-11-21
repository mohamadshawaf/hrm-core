"""Provision an independent platform owner locally; never via a public API."""

from getpass import getpass
import os
import sqlite3
from uuid import uuid4

from .database import UNIQUE_ERRORS, initialize, session
from .schemas import _email
from .security import hash_password


def create_platform_owner(db_path: str, *, email: str, password: str) -> str:
    normalized_email = _email(email)
    if normalized_email is None:
        raise ValueError('Platform owner email is required')
    password_hash = hash_password(password)
    admin_id = str(uuid4())
    initialize(db_path)
    try:
        with session(db_path) as connection:
            connection.execute(
                'INSERT INTO platform_admins(id,email,password_hash,role) '
                "VALUES (?,?,?,'platform_owner')",
                (admin_id, normalized_email, password_hash),
            )
    except UNIQUE_ERRORS as error:
        raise ValueError('Platform owner email already exists') from error
    return admin_id


def main() -> None:
    db_path = os.getenv('HRM_DATABASE_URL') or os.getenv('HRM_DB_PATH', './data/hrm_dev.sqlite3')
    print('Create a PLATFORM owner; this account is separate from company owners.')
    email = input('Platform owner email: ').strip()
    password = getpass('Platform owner password (min 12 characters): ')
    if password != getpass('Confirm password: '):
        raise SystemExit('Passwords do not match')
    create_platform_owner(db_path, email=email, password=password)
    print('Platform owner created successfully')


if __name__ == '__main__':
    main()
