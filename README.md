# HRM Core — multi-tenant HR management

**For GitHub reviewers:** This repository demonstrates a full-stack HRM
vertical slice developed by **Mohamad Alshawaf**. Start with the
[architecture](docs/ARCHITECTURE.md),
[engineering case study](docs/PORTFOLIO_CASE_STUDY.md), and
[fictional demo walkthrough](docs/DEMO_AND_CAPTURE_AR.md).
The application is not commercially launched; Android, iOS, Web and live
PostgreSQL verification remain pending external build/test environments.

This is an independent rebuild of the HRM product's first usable vertical
slice. The original Flutter UI prototype remains in a separate private audit
snapshot. This directory contains a **new** Flutter client and a **new**
authenticated API; neither imports the legacy marketplace UI template.

**Developer and project maintainer:** Mohamad Alshawaf. This independent
source snapshot does not include Omran Group client data or legacy assets.
No public redistribution license has been selected yet.

## Implemented

- Backend: FastAPI API with request validation, temporary SQLite development
  storage, scrypt password hashing, 15-minute session-bound signed access
  tokens, and organization-scoped data access.
- Roles: `owner` and `hr` may add/edit/archive employees; `viewer` has
  read-only access. Authorization is checked by the server on every request.
- **Company user management:** a company `owner` can invite HR managers and
  read-only viewers by 48-hour single-use email codes. Recipients choose
  their own passwords. Owners can change roles and activate/deactivate users,
  but cannot modify an owner or grant platform privileges. The previous
  direct password-creation API returns `410` by default.
- **Password recovery:** non-enumerating requests, 30-minute single-use codes,
  60-second cooldown, and immediate revocation of all sessions on reset.
- **Device sessions:** 15-minute JWT access tokens bind to a revocable device
  session, refresh tokens rotate on each use (30-day maximum lifetime), and
  replay of an old refresh token revokes the affected session. List sessions,
  revoke individual devices, sign out current device, or sign out everywhere.
- **Phase 6 security:** persistently throttled login, registration, recovery,
  email verification, refresh and invitation endpoints. IPs and account IDs
  are kept as HMAC digests in fixed-window rate-limit counters; client-supplied
  `X-Forwarded-For` is ignored. Behind a real load balancer, this still needs
  trusted network-edge enforcement and distributed-abuse detection.
- **Optional transactional email queue:** setting `HRM_MAIL_OUTBOX_KEY` makes
  registration/invitation/recovery append AES-256-GCM-encrypted jobs atomically
  with the authentication changes. A separate worker sends/retries messages
  and erases ciphertext on success. Without the key, local development keeps
  the original immediate sender/outbox behavior.
- **Self-service company registration:** an owner can create an independent
  organization from Flutter. The account stays `pending_email` until its
  owner verifies a 30-minute one-time code. Tokens are random and stored only
  as SHA-256 digests in the database; pending/suspended companies cannot
  sign in or use existing JWTs. An expired verification code can be resent
  after a 60-second cooldown, invalidating older codes.
- Employee records: server-validated create/read/list/update/soft archive;
  pagination, search, duplicate-code prevention, optimistic version checks.
- **Platform administration:** a separately provisioned `platform_owner`
  account has a distinct credential database table, distinct JWT secret,
  issuer and audience. The platform owner can view company summaries, suspend
  or reactivate verified companies, create plan definitions and change manual
  subscription metadata. Tenant users cannot reach platform admin endpoints,
  and platform JWTs cannot access tenant employee endpoints.
- **Subscription foundation:** each new or locally bootstrapped organization
  receives a free `Starter Trial` plan with a nominal 14-day period and a
  descriptive capacity of 25 employees. Plans use **integer halalas** for
  prices; subscription changes use a version check and platform audit log.
  **No payment processing or billing exists.** Subscription status/expiry
  gating and employee capacity checks exist but remain **OFF by default**.
  `HRM_ENFORCE_SUBSCRIPTIONS=1` opts in after the business rules are approved.
- Security evidence: verified registration plus an optional local interactive
  CLI bootstrap; mutation audit events with changed _field names_, not
  sensitive field contents.
- Flutter UI: real sign-in, employee list/search/pagination, add/edit/archive
  dialogs; self-registration, email verification and a responsive platform
  administration dashboard for company overview, status, plans and manual
  subscription management.
- **Milestone 7:** add an initial Arabic/English locale switcher with real
  Flutter Material/Widgets/Cupertino localization delegates, RTL/LTR support
  in the primary sign-in and employee workflows, an adaptive wide-screen
  sign-in panel and compact employee actions on mobile-sized layouts.
- **Safe portfolio demo:** `app.demo_seed` can generate two fictitious
  companies (8 and 12 different employees) in an exclusively created local
  SQLite database. Existing files are never overwritten. Dedicated tests
  verify the seeded accounts remain separated through the authenticated API.
- **GitHub documentation and guardrails:** architecture diagrams, case study,
  screenshot capture guide and a non-destructive scanner for accidental
  local databases, keys and credentials before publication.
- Tests: backend integration suites covering authentication, onboarding,
  verification expiry/replay, validation, CRUD, role permissions, version
  conflicts, organization suspension and tenant isolation. Phase 6 adds tests
  of throttling, encrypted email queues, retries and metadata retention.
- PostgreSQL connection path: optional Psycopg 3 adapter, distinct from local
  SQLite storage. The adapter validates that all three SQL migrations have been
  applied before use. It is **not live-tested against PostgreSQL in this
  environment** because the driver/server are unavailable.

## Architecture

```text
backend/
  app/
    main.py          # API boundary, dependency authorization
    schemas.py       # validated request/response contracts
    database.py      # replaceable local database adapter
    postgres_adapter.py # Psycopg execution and migration prerequisite checks
    user_repository.py # company-owned HR/viewer account management
    invitation_repository.py # one-time company user invitations
    rate_limiter.py  # HMAC-hashed persistent request counters
    mail_queue.py / mail_worker.py # encrypted transactional delivery
    maintenance.py # explicit cleanup of expired auth/email metadata
    password_reset_repository.py # password recovery and session revocation
    session_repository.py # refresh rotation and per-device revocation
    subscription_policy.py # opt-in plan/employee-seat enforcement
    repositories.py  # organization-scoped persistence and audit events
    schema.sql       # relational schema and indexes
    security.py      # password hashing and JWT validation
    mailer.py        # SMTP SSL sender or private local-development outbox
    bootstrap.py     # interactive owner provisioning
    platform_bootstrap.py  # separate local platform-owner provisioning
    platform_repository.py # platform-only persistence and audit events
  postgres/
    001_initial.sql  # baseline schema
    002_user_management.sql # adds account version for concurrency checks
    003_sessions_invitations.sql # sessions, invitations and password resets
    004_security_delivery.sql # request throttling and encrypted mail queue
    README.md        # local database setup and PostgreSQL release gates
  tests/
flutter_client/
  lib/
    core/api_client.dart
    features/auth/   # sign-in, registration, verification; in-memory session
    features/employees/  # entity, repository and responsive UI
    features/platform/   # separate administrator login and web/mobile dashboard
    features/organization/  # company owner user management
```

This is a _vertical slice_, not completion of attendance, leave, payroll or
other HR modules. The local SQLite adapter is intentionally isolated; use
PostgreSQL with controlled migrations before deploying publicly. The optional
Psycopg code path is now selectable in development via `HRM_DATABASE_URL`,
but a real database must be provisioned, migrated and tested independently.
See `API.md` for the supported endpoint contracts and error responses.
See `ROADMAP_AR.md` for the full HRM implementation sequence and release gates.
See `SECURITY_REVIEW.md` for the milestone's threat/control matrix and
remaining deployment blockers.
See `RELEASE_PLAN_AR.md` for the roadmap to a job-search GitHub portfolio,
an internal pilot and a commercial SaaS release.
See `docs/PORTFOLIO_CASE_STUDY.md` for recruiter-facing capability/evidence
claims and their explicit limits. Screenshots are **not yet included** because
they must be captured from an actually running Flutter build.
See [`docs/STAGE7_QA_AR.md`](docs/STAGE7_QA_AR.md) for the precise local
test evidence and release blockers.

## Backend: local run

Python 3.12+ is recommended for this snapshot.

```sh
cd backend
python -m venv .venv
# Activate your venv using the command for your OS
python -m pip install -r requirements-dev.txt
python -m app.bootstrap
```

Choose a unique organization code, owner email, and password. The password is
entered interactively and is not passed as a shell argument.

### Try a fictional, isolated two-company demo (milestone 7)

From `backend/`, create a local directory and a brand-new database:

```sh
mkdir -p data
python -m app.demo_seed --db-path ./data/demo.sqlite3 --confirm-demo
```

The CLI prompts for a demo-only password. It creates `atlas-demo` (8 sample
employees, `owner@atlas.example.invalid`) and `cedar-demo` (12 sample
employees, `owner@cedar.example.invalid`). Run the server with
`HRM_DB_PATH=./data/demo.sqlite3`, a fresh `HRM_JWT_SECRET`, and a separate
`HRM_PLATFORM_JWT_SECRET`. These fictional local accounts are for showcasing
tenant isolation and must never receive real employee data. For Windows
PowerShell steps, Flutter setup and a truthful screenshot checklist, see
[`docs/DEMO_AND_CAPTURE_AR.md`](docs/DEMO_AND_CAPTURE_AR.md).

### Enable the platform administration dashboard locally

The platform owner is **not** a tenant/company owner. Provision this account
on the backend machine using a separate interactive command:

```sh
cd backend
python -m app.platform_bootstrap
```

Set two **different** randomly generated JWT signing secrets before running
the server (the platform API responds with `503` when its secret is absent):

```sh
# Unix shells only
export HRM_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export HRM_PLATFORM_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
$env:HRM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:HRM_PLATFORM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

In Flutter, choose **Platform administration** below the standard company
login form. Sign in with the account created using the platform bootstrap CLI.
It has separate overview, company-management and plan-management sections.

### Manage employees' login accounts as a company owner

After signing into a company as `owner`, select **Company users** in the
employee management toolbar. The owner can invite an `hr` or `viewer` by email,
then manage roles and account activation. Invitations expire after 48 hours;
the invitee selects **Accept a company invitation** on the sign-in screen,
enters their one-time code and sets their own password. HR managers and viewers
cannot access company user management. Password recovery is on the same login
screen via **Forgot password?**. It revokes all devices after a successful reset.

### Optional PostgreSQL development path

The `psycopg[binary]` dependency is declared in `requirements.txt`. With a
**disposable** local PostgreSQL instance, apply `backend/postgres/001_initial.sql`
then `002_user_management.sql`, `003_sessions_invitations.sql`, and
`004_security_delivery.sql` as described
in `backend/postgres/README.md`.
Configure the backend environment with `HRM_DATABASE_URL` set to that local
database URL. This overrides the SQLite `HRM_DB_PATH`.

Do not point this development application at production data or assume
PostgreSQL parity: it needs real PostgreSQL integration tests, connection
pooling, controlled upgrades and backup verification first. The backend still
intentionally refuses to run with `HRM_ENV=production`.

**Company owners may now register through the Flutter interface** without CLI
access. They enter the company name, unique company code, owner email, and a
password with at least 12 characters. Registration returns `202`, with no
login token. A verification code is delivered separately; after verification,
the owner can sign in.

### Email delivery in local development

In the default local-development mode, an email is **not** actually sent.
Instead, the one-time code is written to a restricted local file beside the
SQLite database: `data/verification-outbox.txt` (one `email<TAB>code` per line,
with owner-only file permissions on supported systems). Paste the code into
the Flutter verification screen. **Never publish, copy to GitHub or use this
outbox with real addresses or employee information.**

Company invitation and password reset codes use separate restricted local
outboxes: `data/invitation-outbox.txt` and `data/reset-outbox.txt`. Neither
code is included in the API response. Never commit these files to GitHub.

### Optional durable transactional delivery (phase 6)

For asynchronous email processing, generate a **random 32-byte key** (64 hex
characters) and place it in the backend's private environment as
`HRM_MAIL_OUTBOX_KEY`. The backend and worker must use the same key. Do not
rotate this key without a documented re-encryption/drain plan.

Once configured, API requests enqueue encrypted email payloads rather than
sending SMTP while holding a database transaction. Run the worker regularly
from a separate process (or a scheduler):

```sh
cd backend
python -m app.mail_worker --max-jobs 50
```

After reviewing your retention policy, remove expired token history and
finished job metadata with:

```sh
python -m app.maintenance --confirm
```

Delivery is **at least once**: a worker crash after SMTP success and before
marking sent may cause a duplicate message containing the same valid code.
Failed jobs retry with exponential delay up to five attempts. Production
still needs monitoring, alerting, dead-letter inspection and rate limiting at
the trusted network edge.

To send through an existing SMTP-over-TLS/SSL provider (port 465 by default),
set these variables in the backend environment:

```text
HRM_SMTP_HOST=smtp.example.com
HRM_SMTP_PORT=465
HRM_SMTP_USERNAME=your-smtp-account
HRM_SMTP_PASSWORD=your-secret
HRM_SMTP_FROM=verification@example.com
```

Only configure the sender in a secure local development environment. A
production deployment will additionally need a durable email queue,
resilient delivery retries, stronger resend abuse prevention, rate limiting
and delivery monitoring.
No secret is returned by the registration HTTP response.

For deterministic tests without a server:

```sh
cd backend
python -m unittest discover -s tests -v
```

A GitHub Actions workflow at `.github/workflows/ci.yml` is included. When
run inside an actual GitHub repository, it provisions **disposable PostgreSQL**
for live API integration tests, runs Flutter static analysis/unit tests and
attempts Android and Web builds. The unsigned iOS build runs on manual
`workflow_dispatch` to control macOS runner cost. **The workflow has not
run yet; adding a workflow file alone is not evidence of passing builds.**
The workflow also runs a basic private-artifact filename check. Review git
history and run a dedicated secret scanner before publishing; the basic check
alone cannot guarantee a clean history.

The interactive API reference is accessible locally at
`http://127.0.0.1:8000/docs`.

## Flutter: local run

The Flutter SDK and platform scaffolding were not supplied. In
`flutter_client/`, use an installed Flutter SDK to generate native scaffolding
for the desired platform _without overwriting the supplied lib files_:

```sh
flutter create --platforms=android,ios,web .
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=HRM_API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the Android emulator's route to the host machine. For Flutter
web, set `HRM_CORS_ORIGINS` on the backend to the exact frontend origin (for
example `http://localhost:53512`) and configure the correct backend address.
For Flutter desktop, configure the correct local address. HTTP is accepted only
in **debug** builds; release builds require an HTTPS URL. iOS builds require
an appropriate Apple build environment.

The Flutter UI has **not** been compiled here because no Flutter/Dart SDK is
installed. Its model, layout and Arabic/English widget tests are included but
unverified pending `flutter test`. Some auxiliary dialogs remain in English;
the bilingual catalog is a first pass, not a completed translation audit.

## Deployment blockers

1. Exercise the new PostgreSQL adapter against a disposable PostgreSQL server,
   then implement managed migrations, safe backups/restore drills, connection
   pooling, a SQLite-to-PostgreSQL migration plan and environment-specific setup.
2. Enforce HTTPS, production-grade IP/device abuse prevention at the trusted
   edge, secrets storage, operational email monitoring and a recovery playbook.
   Access/refresh tokens stay in Flutter memory, not local browser storage;
   restarting the app requires sign-in. Access tokens expire after 15 minutes.
3. Complete employee self-service roles, approved subscription/billing policy,
   payment processing, tenant-level policy and
   employee PII retention/deletion. Perform a security assessment before production.
4. Add full mobile/web integration testing, release build verification, crash
   reporting, observability, accessibility and realistic performance profiling.
5. Extend end-to-end tests and implement attendance, leave, payroll, and files.
6. Confirm the original template's licensing separately if legacy code/assets
   are ever migrated; the new client does not depend on them.

The backend **refuses to start** when `HRM_ENV=production` until the storage
and security work above has actually been completed.

**Never upload employee records, production databases, or secrets to GitHub.**
#   h r m - c o r e  
 