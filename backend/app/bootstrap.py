"""Local owner bootstrap: no public account-creation endpoint."""

from getpass import getpass
import os
import re
import sqlite3
from uuid import uuid4
import time

from .database import STARTER_PLAN_ID, TRIAL_DURATION_SECONDS, UNIQUE_ERRORS, initialize, session
from .schemas import _email
from .security import hash_password


def create_organization_owner(
    db_path: str, *, code: str, name: str, email: str, password: str,
) -> tuple[str, str]:
    if not re.fullmatch(r"[a-z0-9_-]{2,40}", code):
        raise ValueError("Organization code must be lowercase alphanumeric, _ or -")
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError("Organization name must be 1-120 characters")
    normalized_email = _email(email)
    if normalized_email is None:
        raise ValueError("Email is required")

    organization_id, user_id = str(uuid4()), str(uuid4())
    password_hash = hash_password(password)
    initialize(db_path)
    try:
        with session(db_path) as connection:
            connection.execute(
                "INSERT INTO organizations(id, code, name) VALUES (?, ?, ?)",
                (organization_id, code, name.strip()),
            )
            connection.execute(
                "INSERT INTO users(id, organization_id, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, 'owner')",
                (user_id, organization_id, normalized_email, password_hash),
            )
            connection.execute(
                "INSERT INTO organization_subscriptions "
                "(organization_id,plan_id,status,period_ends_at) "
                "VALUES (?, ?, 'trialing', ?)",
                (organization_id, STARTER_PLAN_ID, int(time.time()) + TRIAL_DURATION_SECONDS),
            )
    except UNIQUE_ERRORS as error:
        raise ValueError("Organization code is already in use") from error
    return organization_id, user_id


def main() -> None:
    db_path = os.getenv('HRM_DATABASE_URL') or os.getenv("HRM_DB_PATH", "./data/hrm_dev.sqlite3")
    print("Create the first HRM organization owner (local CLI only)")
    code = input("Organization code: ").strip()
    name = input("Organization name: ").strip()
    email = input("Owner email: ").strip()
    password = getpass("Owner password (min 12 characters): ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    create_organization_owner(db_path, code=code, name=name, email=email, password=password)
    print("Organization owner created successfully")


if __name__ == "__main__":
    main()
