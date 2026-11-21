# HRM Core — Full-Stack Engineering Case Study

**Author:** Mohamad Alshawaf  
**Product:** Independent, multi-organization human resources management
system — early engineering preview.  
**Stack:** Python, FastAPI, Pydantic, SQLite (local testing), PostgreSQL
(adapter + migration files), Flutter/Dart, GitHub Actions.

## Problem

Provide separate workspaces for organizations to manage employee records,
their HR accounts and device sessions, while allowing a platform owner to
monitor company status without access to tenant employee endpoints.

## My responsibilities in this repository

- Structured an independent client/server implementation rather than depending
  on the original client-specific Flutter template.
- Implemented FastAPI request validation, tenant-scoped persistence,
  role-based access, optimistic locking and audit logging.
- Implemented company registration, email verification, invitations, password
  resets, session refresh/revocation and a separate platform-owner API.
- Added a Flutter client for login, employee CRUD and platform management,
  including responsive layout work and initial Arabic/English switching.
- Added SQLite integration tests, an opt-in PostgreSQL integration suite and
  GitHub Actions configuration for backend and Flutter platform verification.
- Created isolated fictional demo data in a new local SQLite file with
  safety checks against overwriting existing databases.

## Demonstrated engineering decisions

| Requirement | Implementation | Evidence location |
| --- | --- | --- |
| Tenant isolation | Server derives `organization_id` from the signed-in user | `backend/app/main.py`, `repositories.py`, `tests/test_stage7_demo.py` |
| Auditable mutations | Employee changes and entity IDs recorded with field names | `backend/app/repositories.py` |
| Account security | Password hashing, JWT/session handling, rate limiting | `backend/app/security.py`, `session_repository.py`, `rate_limiter.py` |
| Operational delivery | Optional transactional encrypted job queue | `backend/app/mail_queue.py`, `mail_worker.py` |
| Multiple interfaces | Flutter shared client plus responsive desktop/mobile views | `flutter_client/lib/` |
| Delivery discipline | CI YAML, backend tests, conservative release gates | `.github/workflows/ci.yml`, `QA_RUNBOOK_AR.md` |

## Validation and honest limitations

- Local tests use a disposable SQLite database, including adversarial
  permission cases, tenant separation, replay/revocation and demo fixtures.
- The PostgreSQL server and Flutter SDK were **not available** in the authoring
  environment. Do not describe the application as Android/iOS/Web *tested* or
  PostgreSQL *production validated* until CI/device evidence exists.
- The Flutter interface has bilingual primary workflows, but not all minor
  screens have undergone full localization and accessibility QA.
- This is not a completed payroll, attendance, leave or commercial billing
  application. No production customer deployment is claimed.
- Never show confidential Omran Group records or private client assets in
  screenshots or the repository.

## Portfolio talking points

1. **Full-stack boundaries:** independent Flutter client and authenticated
   FastAPI service, with organization data scopes enforced server-side.
2. **Security-centric data model:** separate platform identity, session
   rotation, audit events, invitation/password-reset token lifecycle.
3. **Delivery discipline:** repeatable tests, explicit release blockers,
   versioned PostgreSQL migrations and safe synthetic demo data.

## Product roadmap

Before a public live demo: run successful CI, verify cross-platform builds,
complete translation, perform security/privacy review and deploy a disposable
backend with HTTPS. Before commercial launch: implement the missing HR domain
features, PostgreSQL operations, reliable monitoring/backup and compliance.

**License:** Not selected. Do not imply an open-source license before one is
chosen and any third-party rights have been reviewed.
