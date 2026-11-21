# HRM Core API contract - milestone 6

Base path: `/api/v1`  
Authentication: `Authorization: Bearer <access_token>` (15-minute JWT)  
Transport: HTTPS required for any non-local deployment.

| Method | Path | Required role | Purpose |
| --- | --- | --- | --- |
| `POST` | `/organizations/register` | Public | Register an independent company and owner; await email verification |
| `POST` | `/organizations/verify-email` | Public; valid one-time code | Activate pending company |
| `POST` | `/organizations/resend-verification` | Public | Request a fresh code for a pending company (60-second cooldown) |
| `POST` | `/auth/token` | Public; valid organization and credentials | Obtain session-bound access and rotating refresh tokens |
| `POST` | `/auth/refresh` | Valid single-use refresh token | Rotate refresh token; issue fresh access token |
| `GET` | `/auth/sessions` | Authenticated | List up to 100 of your device sessions |
| `DELETE` | `/auth/sessions/{id}` | Authenticated | Revoke your own device session |
| `POST` | `/auth/logout` | Authenticated | Revoke current session |
| `POST` | `/auth/logout-all` | Authenticated | Revoke all own sessions |
| `POST` | `/auth/password-resets/request` | Public | Request recovery email (uniform `202` response) |
| `POST` | `/auth/password-resets/confirm` | Valid one-time code | Update password and revoke all sessions |
| `GET` | `/auth/me` | Authenticated | Current user identity and role |
| `GET` | `/employees` | Authenticated | Search, paginate, filter archived records |
| `GET` | `/employees/{id}` | Authenticated | Read employee in own organization |
| `POST` | `/employees` | `owner`, `hr` | Create employee |
| `PATCH` | `/employees/{id}` | `owner`, `hr` | Update with expected version |
| `DELETE` | `/employees/{id}` | `owner`, `hr` | Soft archive with expected version |
| `GET` | `/organization/users` | Company `owner` | Paginated company users and roles (no password fields) |
| `POST` | `/organization/users` | Company `owner` | **Deprecated** direct password creation; `410` by default |
| `POST` | `/organization/invitations` | Company `owner` | Email invitation for `hr` or `viewer` |
| `GET` | `/organization/invitations` | Company `owner` | List invitations without secrets |
| `POST` | `/organization/invitations/accept` | Public; valid code | Set own password and activate invited account |
| `PATCH` | `/organization/users/{id}` | Company `owner` | Change `hr`/`viewer` role or active state with version check |
| `POST` | `/platform/auth/token` | Platform-owner credentials | Obtain separate 15-minute platform access token |
| `GET` | `/platform/auth/me` | Platform owner only | Current platform administrator |
| `GET` | `/platform/overview` | Platform owner only | Organization and employee counts |
| `GET` | `/platform/organizations` | Platform owner only | Paginated company summaries; search by name/code |
| `PATCH` | `/platform/organizations/{id}/status` | Platform owner only | Suspend/reactivate an email-verified company |
| `GET` | `/platform/plans` | Platform owner only | List plan metadata |
| `POST` | `/platform/plans` | Platform owner only | Create plan metadata |
| `PATCH` | `/platform/organizations/{id}/subscription` | Platform owner only | Change manual subscription metadata using optimistic version |

## Platform administration separation

Provision an account from the backend machine using
`python -m app.platform_bootstrap`, never from public registration endpoints.
The `platform_owner` user exists in a dedicated `platform_admins` table and
uses `HRM_PLATFORM_JWT_SECRET`, with a distinct JWT issuer and audience.
**Company owner or HR credentials and tokens do not authorize these routes.**

`POST /platform/auth/token` accepts:

```json
{ "email": "admin@platform.example", "password": "your-secret" }
```

`POST /platform/plans` accepts:

```json
{
  "code": "business",
  "name": "Business Plan",
  "price_halalas": 29900,
  "max_employees": 250
}
```

The price above is an **example**, not a real subscription offer. All prices
are integer Saudi halalas (`29900` = 299.00 SAR). No money changes hands.

`PATCH /platform/organizations/{id}/status` accepts
`{ "status": "suspended" }` or `{ "status": "active" }`. It cannot bypass
pending email verification: a `pending_email` organization gets `409`.
Suspension invalidates its users' currently issued JWTs immediately.

`PATCH /platform/organizations/{id}/subscription` accepts:

```json
{
  "plan_id": "00000000-0000-4000-8000-000000000001",
  "status": "trialing",
  "period_ends_at": 1797379200,
  "expected_version": 1
}
```

`period_ends_at` is a UTC Unix timestamp in seconds. The update returns
`409` if another administrator changed the record after the listed version.
An organization is created with default free trial **metadata** (provisional
14 days, 25 seats). Plan status, employee capacity and period end are enforced
only when `HRM_ENFORCE_SUBSCRIPTIONS=1` (default `0`). This setting requires
approval of trial/renewal rules before activation. When enabled, `past_due`,
`canceled` or expired subscriptions receive `403`, and reaching the active
employee seat limit returns `409`. **No payment or billing is implemented.**

## Company user management

Company owners use **company access tokens**, not platform-owner tokens.
The user directory is limited to the current company and supports pagination:

`GET /api/v1/organization/users?limit=20&offset=0`

`POST /api/v1/organization/invitations`:

```json
{
  "email": "hr-manager@company.example",
  "role": "hr"
}
```

An email sender receives the random invitation code (or it is placed in the
restricted local dev outbox). The `202` response includes no token. An invite
expires in 48 hours, is single-use and has a per-address 60-second cooldown.
The invitee uses `POST /organization/invitations/accept` with
`{ "token": "...", "password": "a-private-password-12+" }`. Company owners
cannot invite other owners or platform admins. `GET /organization/invitations`
contains metadata only, with no tokens. The old direct-password account API is
disabled with `410` unless the server is explicitly created with
`allow_legacy_user_creation=True` for development compatibility tests.

`PATCH /api/v1/organization/users/{id}`:

```json
{
  "expected_version": 1,
  "role": "viewer",
  "is_active": false
}
```

Updates are organization-scoped, check the expected version, and log only the
changed field names. `is_active=false` invalidates access and refresh immediately.
Employee personal portals remain out of scope.

## Login payload

```json
{
  "organization_code": "your-org-code",
  "email": "your-email@example.com",
  "password": "your-password",
  "device_label": "HRM Web"
}
```

Returns `access_token`, `refresh_token`, `token_type`, `expires_in=900`,
`refresh_expires_in`. Refresh tokens rotate with `POST /auth/refresh` accepting
`{ "refresh_token": "..." }`. The server stores only SHA-256 token digests and
an immutable 30-day session expiry. Reusing an already-consumed refresh token
immediately revokes its device session. `/auth/sessions` lists device labels,
expiry and revocation state. The client holds secrets in memory only; no
persisted cross-restart login is promised.

`POST /auth/password-resets/request` accepts
`{ "organization_code": "your-org-code", "email": "you@example.com" }`.
Responses are identical for known/unknown accounts. After receiving the code,
`POST /auth/password-resets/confirm` accepts
`{ "token": "...", "new_password": "12-or-more-characters" }`.
Reset codes expire after 30 minutes; a successful reset revokes all sessions.

## Request throttling and transactional email delivery

Every login attempt counts against two independent database-backed
fixed-window buckets: a per-request-origin bucket (600 attempts in 15 minutes)
and a per-company/email bucket (15 attempts in 15 minutes). Other sensitive
endpoints, including platform login, company registration, invitations,
verification and recovery, also have purpose-specific buckets and return
`429` with `Retry-After` on exhaustion. Identifiers are stored as HMAC digests;
the API does not trust spoofed `X-Forwarded-For` headers. These are baseline
controls only: distributed attacks still require network-edge enforcement.

`HRM_MAIL_OUTBOX_KEY` (64 hex digits representing 32 random bytes) enables
atomic encrypted mail enqueueing during registration, invitation and recovery.
Queued one-time codes are decrypted only inside a separate worker, which
retries failed sends and removes ciphertext after delivery. If the key is
absent, only the synchronous local-development sender is used. No secret
appears in a normal HTTP success response.

An organization in `pending_email` or `suspended` status cannot sign in. An
existing access token immediately stops working after suspension because its
user and organization state is checked on every authenticated API call.

## Self-service registration

```http
POST /api/v1/organizations/register
Content-Type: application/json
```

```json
{
  "organization_code": "your-company",
  "organization_name": "Your Company Name",
  "owner_email": "owner@example.com",
  "password": "a-long-private-password"
}
```

Response `202`:

```json
{
  "status": "pending_email",
  "message": "Registration received. Verify the owner email to activate the organization."
}
```

The server delivers a private, random code out-of-band (see the README local
development outbox or SMTP SSL configuration); neither code nor token hash is
exposed in this response. To activate:

```http
POST /api/v1/organizations/verify-email
Content-Type: application/json
```

```json
{ "token": "paste-the-full-code-from-the-email" }
```

Returns `200` with `{ "status": "active", ... }`. Codes expire 30 minutes
after registration, are single-use, and cannot be exchanged for session tokens
without the password. There is **no** public endpoint to assign an `owner`,
`hr`, or `viewer` role in an existing organization.

If the code expires, `POST /api/v1/organizations/resend-verification` accepts
`{ "organization_code": "your-company", "owner_email": "owner@example.com" }`.
The response is always `202` with a generic message (including for unknown
companies or addresses); only a matching **pending** company receives a code.
Requests made within 60 seconds of the previous send are ignored. A newly
issued code revokes all earlier unconsumed codes. This minimum cooldown is not
a substitute for production-grade IP/account abuse prevention.

## Create employee payload

```json
{
  "employee_code": "EMP-001",
  "full_name": "Example Employee",
  "job_title": "Software Developer",
  "department": "Engineering",
  "email": "employee@example.com",
  "phone": null,
  "hire_date": "2024-02-15",
  "status": "active"
}
```

`PATCH` permits `full_name`, `job_title`, `department`, `email`, `phone`,
`hire_date`, and `status`, alongside the **required** `expected_version`
integer to avoid silently overwriting concurrent edits. Employee code and
organization cannot be changed through this endpoint.

## Search and pagination

`GET /employees?search=Example&limit=25&offset=0` returns:

```json
{
  "items": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

## Expected errors

- `401` missing, invalid or expired credentials.
- `403` insufficient role permissions.
- `404` record does not exist **in the authenticated organization**.
- `409` duplicate employee code or stale `expected_version`.
- `409` organization registration code already registered.
- `409` employee plan seat limit reached (only when policy enabled).
- `410` direct password creation superseded by invitations.
- `429` invitation per-recipient resend cooldown.
- `429` rate-limit bucket exceeded, including repeated login attempts.
- `403` inactive/expired subscription (only when policy enabled).
- `400` invalid, used or expired verification code.
- `503` email delivery failed (the local registration transaction is rolled back).
- `422` invalid input or missing required fields.

## Audit and privacy

Employee create, update and archive actions are recorded atomically with the
data change. The audit table stores field **names**, actor ID, organization,
entity ID and timestamp; it does not store password or employee field values.

These endpoints are implemented in the milestone backend and covered by
automated tests. They are not a complete HRM platform or deployment approval.
