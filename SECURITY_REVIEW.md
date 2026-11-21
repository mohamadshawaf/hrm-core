# HRM Core - Milestone 6 security review and deployment gates

**Not a production approval.** The backend explicitly rejects
`HRM_ENV=production` until the deployment/security work is completed.

## Controls implemented and locally tested

| Concern | Implemented control | Remaining requirement |
| --- | --- | --- |
| Cross-company access | Server-side organization-scoped employee/user queries | Live PostgreSQL isolation tests and defense-in-depth policy review |
| Employee onboarding | Owner-only, random 48-hour invitation code stored as a SHA-256 digest; recipient selects password | Delivery queue, per-IP rate limits and invitation cancellation |
| Password recovery | Single-use 30-minute token, 60-second per-account cooldown, uniform request response; revoke all sessions after change | Production delivery telemetry, rate limits and anti-abuse |
| Lost device | Per-device server session; immediate access and refresh-token revocation; logout everywhere | Persistent session UX choice and client secure-storage review |
| Refresh token replay | One-time rotation; previous digest retained for replay detection, which revokes its device | Scheduled expiry cleanup, concurrent PostgreSQL integration tests |
| Employee capacity | Transactionally reserve the company subscription row before counting active employees | Approved subscription limits, simultaneous-write PostgreSQL tests |
| Trial expiration | Opt-in status and expiry gate, disabled by default | Approved billing/trial lifecycle and dispute/grace-period policy |
| Password storage | Salted scrypt hashing with bounded work factors | Credential rate limiting, credential compromise process |
| Audit trail | Field-name-only employee/role/password reset audit records | Immutable/retained logs and admin investigation tools |
| Brute-force and spam | Per-IP and per-account fixed-window HMAC-hashed rate counters in database | Trusted edge rate limits, distributed attack detection, MFA and risk controls |
| Email delivery | Optional AES-GCM transactional queue, leased workers, retries and ciphertext deletion on success | Monitor dead jobs, sender reputability and email delivery outcomes |
| Expired auth metadata | Opt-in retention cleanup command with explicit confirmation | Schedule, measure, and review retention against privacy rules |

## Intentional security decisions

- The Flutter client keeps access and refresh secrets **in memory only**.
  Closing/reloading the app requires a new login. No cookies or browser
  localStorage are used for authentication in this milestone.
- The API never returns invitation, email-verification or password-reset
  secrets. Default *development* email outboxes contain plaintext codes;
  use fake accounts only and never include these files in source control.
- All company JWTs carry a device session ID; the backend checks the user,
  company status and session revocation on each request.
- Owners cannot assign `owner`/`platform_owner` through invitations. Legacy
  password-based user creation is disabled by default with HTTP `410`.
- Subscription enforcement is disabled by default because the provisional
  14-day/25-employee trial is **not an approved commercial policy**.
- Signing out and managing existing sessions are still available to users
  whose trial expires, provided their company and own user account remain
  active. Business data endpoints reject inactive subscriptions when enabled.

## Blocking work before real users or GitHub publication

1. Run the prepared CI (not yet executed), disposable PostgreSQL integration,
   concurrency and rollback tests;
   install controlled migrations, connection pooling and verified backups.
2. Build/analyze/test Flutter on **Android, iOS, and Web**, including
   responsive layout, accessibility and failed-network recovery.
3. Deploy HTTPS with HSTS/CSP, carefully scoped CORS, network-edge and
   distributed rate limits, MFA, authentication monitoring and security alerting.
4. Configure and monitor the encrypted email worker and retention scheduler,
   test crash recovery, retries and secret rotation; document dead job handling.
5. Approve the exact subscription policy, billing integration, privacy
   retention rules and Saudi hosting/data-processing requirements.
6. Complete authorization matrix and threat-model reviews for every future
   attendance, leave, payroll and document endpoint.

**Never upload real HR records, access tokens, reset codes, secrets, local
email outboxes or development databases to a public repository.**
