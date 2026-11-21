# PostgreSQL development adapter and schema preparation

`001_initial.sql`, `002_user_management.sql`, and
`003_sessions_invitations.sql` and `004_security_delivery.sql` are sequential schema steps
for a **new empty PostgreSQL database**. They are not a data migration from
SQLite. Neither migration nor the new Psycopg runtime adapter has been tested
against a real PostgreSQL server in this environment.

For a local disposable database, after provisioning PostgreSQL with a dedicated
database and user, a database administrator can inspect and apply the script:

```sh
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  --dbname="postgresql://YOUR_LOCAL_USER@localhost:5432/YOUR_EMPTY_DB" \
  --file=001_initial.sql
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  --dbname="postgresql://YOUR_LOCAL_USER@localhost:5432/YOUR_EMPTY_DB" \
  --file=002_user_management.sql
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  --dbname="postgresql://YOUR_LOCAL_USER@localhost:5432/YOUR_EMPTY_DB" \
  --file=003_sessions_invitations.sql
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  --dbname="postgresql://YOUR_LOCAL_USER@localhost:5432/YOUR_EMPTY_DB" \
  --file=004_security_delivery.sql
```

Set `HRM_DATABASE_URL=postgresql://...` in the process environment when
running the development API. The backend checks `schema_migrations` for both
steps at startup and refuses to connect to an unmigrated database. Never
provide real production employee information during these tests.

### Optional real PostgreSQL integration smoke test

The standard test suite **skips** the live test. Use an explicitly disposable
PostgreSQL database with a role allowed to create/drop its own test schema.
After installing `requirements-dev.txt`, set both environment variables:

```sh
export HRM_TEST_POSTGRES_DSN='postgresql://LOCAL_TEST_USER@127.0.0.1:5432/EMPTY_TEST_DB'
export HRM_PG_TEST_ALLOW_SCHEMA_CREATE=1
python -m unittest tests.test_postgres_live -v
```

The test creates a randomly named schema, applies all four migrations,
checks API login, employee CRUD/audit, invitation queue, refresh rotation and session revocation,
then removes **only its own schema**. Do not provide credentials for any
non-disposable database. This test has **not** been executed here because
PostgreSQL and Psycopg are unavailable in the execution environment.

Before production, the backend still needs:

1. Execute full PostgreSQL integration tests of the newly added Psycopg adapter,
   particularly parameter adaptation, JSONB, concurrent version checks, tenant
   isolation, transaction rollback and bootstrap. Introduce connection pooling.
2. Versioned upgrade/downgrade migrations, schema-drift detection, database
   user privileges, secure connection settings and backups/restoration drills.
3. A verified, explicit SQLite data migration procedure (if migrating actual
   local data) and carefully tested data retention/deletion policies.
4. Tests against the real database: concurrent writes, optimistic locks,
   tenant isolation, transactional email delivery, audit events and failure
   recovery.

**Do not enable HRM_ENV=production yet.** The backend intentionally refuses
production startup while these gates are unfinished.
