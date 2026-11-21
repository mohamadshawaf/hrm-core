"""Create an isolated, entirely fictional SQLite portfolio demo.

Never run this module against an existing HRM database. The CLI refuses to
overwrite any path and will not run in production mode. No actual client,
employee, or company records are copied into the demo.
"""

from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path

from .bootstrap import create_organization_owner
from .database import session
from .repositories import EmployeeRepository


DEMO_COMPANIES = (
    ("atlas-demo", "Atlas Demo Company", "owner@atlas.example.invalid"),
    ("cedar-demo", "Cedar Demo Company", "owner@cedar.example.invalid"),
)

_PEOPLE = (
    ("ليان أحمد", "HR Specialist", "Human Resources"),
    ("Omar Nasser", "Software Developer", "Engineering"),
    ("نورة خالد", "Accountant", "Finance"),
    ("Sara Adel", "Operations Coordinator", "Operations"),
    ("Yousef Salem", "UX Designer", "Design"),
    ("مها عبدالله", "Recruitment Officer", "Human Resources"),
    ("Ali Mansour", "Project Manager", "Operations"),
    ("Dana Kareem", "QA Analyst", "Engineering"),
    ("سعيد محمد", "Finance Analyst", "Finance"),
    ("Hala Ibrahim", "Support Specialist", "Customer Support"),
    ("Rami Khalil", "DevOps Engineer", "Engineering"),
    ("ريم عمر", "Office Administrator", "Operations"),
)


def create_demo_database(db_path: str, *, password: str) -> dict[str, int]:
    """Seed a *new* local SQLite path; never alter an existing database.

    Returns the count of fabricated employees per organization code.
    Passwords are hashed by the normal bootstrap; none are written to files.
    """
    if os.getenv("HRM_ENV", "").lower() == "production":
        raise ValueError("Demo seeding is disabled in production mode")
    if "://" in db_path or db_path == ":memory:":
        raise ValueError("The demo requires an isolated on-disk SQLite path")
    if len(password) < 12:
        raise ValueError("Choose a demo password of at least 12 characters")
    target = Path(db_path).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    if not target.parent.is_dir():
        raise FileNotFoundError("Create the demo database directory first")

    # Exclusive creation closes the check/create race and restricts the file
    # to its owner, regardless of the user's default umask on POSIX systems.
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)

    seeded: dict[str, int] = {}
    for index, (code, name, email) in enumerate(DEMO_COMPANIES):
        org_id, owner_id = create_organization_owner(
            str(target), code=code, name=name, email=email, password=password,
        )
        with session(str(target)) as connection:
            repo = EmployeeRepository(connection, org_id, owner_id)
            # Deliberately different records in each company to demonstrate
            # tenant isolation, plus mixed Arabic/English text and departments.
            count = 8 if index == 0 else 12
            for person_index, (full_name, title, department) in enumerate(_PEOPLE[:count], 1):
                repo.create({
                    "employee_code": f"D{index + 1}-{person_index:03d}",
                    "full_name": full_name,
                    "job_title": title,
                    "department": department,
                    "email": f"demo.{index + 1}.{person_index}@example.invalid",
                    "phone": None,
                    "hire_date": f"202{person_index % 5}-0{(person_index % 9) + 1}-15",
                    "status": "active" if person_index % 5 else "inactive",
                })
        seeded[code] = count
    return seeded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True,
                        help="A NEW SQLite .sqlite3 path in a private local directory")
    parser.add_argument("--confirm-demo", action="store_true",
                        help="Confirm that the chosen path is for fake demo data only")
    args = parser.parse_args()
    if not args.confirm_demo:
        parser.error("Pass --confirm-demo after verifying your isolated database path")
    password = getpass("Choose a DEMO-ONLY password (min 12 chars, never printed): ")
    try:
        seeded = create_demo_database(args.db_path, password=password)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Demo not created: {exc}\n")
    print("Generated entirely fictional sample records:")
    for code, _, email in DEMO_COMPANIES:
        print(f"  {code}: {seeded[code]} employees; login: {email}")
    print("Use the password you entered. Do not upload this database to GitHub.")


if __name__ == "__main__":
    main()
