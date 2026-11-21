"""Authenticated, organization-scoped HRM employee API.

SQLite is used solely for local development and contract tests. Production
deployment requires a PostgreSQL adapter, migrations and deployment hardening.
"""

from dataclasses import dataclass
import hashlib
import logging
import os
import secrets
import sqlite3
import time
from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from .database import UNIQUE_ERRORS, initialize, session
from .mailer import (configured_verification_sender, configured_invitation_sender,
                     configured_password_reset_sender)
from .mail_queue import MailQueue, parse_mail_key
from .rate_limiter import RateLimiter
from .invitation_repository import InvitationRepository
from .password_reset_repository import PasswordResetRepository
from .platform_repository import PlatformRepository
from .user_repository import OrganizationUserRepository
from .repositories import AccountRepository, EmployeeRepository, OrganizationRegistrationRepository
from .schemas import (EmployeeInput, EmployeePage, EmployeePatch, EmployeeResponse,
                      LoginRequest, RegisterOrganizationRequest, VerifyEmailRequest)
from .schemas import (ResendVerificationRequest, RefreshRequest, InvitationInput,
                      InvitationAccept, PasswordResetRequest, PasswordResetConfirm)
from .schemas import (PlatformLoginRequest, PlatformOrganizationStatusChange,
                      PlatformPlanInput, PlatformSubscriptionChange)
from .schemas import (OrganizationUserInput, OrganizationUserPatch,
                      OrganizationUserPage, OrganizationUserResponse)
from .security import (decode_platform_token, decode_token, hash_password,
                       issue_platform_token, issue_token, verify_password)
from .session_repository import UserSessionRepository, REFRESH_TTL_SECONDS
from .subscription_policy import (SubscriptionPolicy, SubscriptionInactive,
                                  EmployeeSeatLimit)


@dataclass(frozen=True)
class Principal:
    user_id: str
    organization_id: str
    role: str
    session_id: str
    subscription_active: bool


_AUTH_SCHEME = HTTPBearer(auto_error=False)


class _ResetDeliveryFailure(Exception):
    """Signal a rollback without disclosing account existence to clients."""


def create_app(*, database_path: str | None = None, jwt_secret: str | None = None,
               verification_sender: Callable[[str, str], None] | None = None,
               platform_jwt_secret: str | None = None,
               invitation_sender: Callable[[str, str, str], None] | None = None,
               password_reset_sender: Callable[[str, str, str], None] | None = None,
               mail_outbox_key: str | None = None,
               enforce_subscriptions: bool | None = None,
               allow_legacy_user_creation: bool = False) -> FastAPI:
    if os.getenv("HRM_ENV", "development") == "production":
        raise RuntimeError("Production startup is disabled until PostgreSQL and required security controls are implemented")
    path = (database_path or os.getenv('HRM_DATABASE_URL') or
            os.getenv("HRM_DB_PATH", "./data/hrm_dev.sqlite3"))
    secret = jwt_secret or os.getenv("HRM_JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("HRM_JWT_SECRET must contain at least 32 characters")
    platform_secret = (platform_jwt_secret if platform_jwt_secret is not None
                       else os.getenv('HRM_PLATFORM_JWT_SECRET', ''))
    if platform_secret and len(platform_secret) < 32:
        raise RuntimeError('HRM_PLATFORM_JWT_SECRET must contain at least 32 characters')
    if platform_secret and platform_secret == secret:
        raise RuntimeError('Platform and tenant JWT secrets must be independent')
    initialize(path)
    send_verification = verification_sender or configured_verification_sender(path)
    send_invitation = invitation_sender or configured_invitation_sender(path)
    send_password_reset = password_reset_sender or configured_password_reset_sender(path)
    configured_key = (os.getenv('HRM_MAIL_OUTBOX_KEY', '') if mail_outbox_key is None
                      else mail_outbox_key)
    outbox_key = parse_mail_key(configured_key) if configured_key else None
    enforce = (os.getenv('HRM_ENFORCE_SUBSCRIPTIONS', '0') == '1' if
               enforce_subscriptions is None else enforce_subscriptions)
    missing_account_hash = hash_password("dummy-password-for-constant-time-checks")
    app = FastAPI(title="HRM Core API", version="0.7.0")
    origins = [x.strip() for x in os.getenv("HRM_CORS_ORIGINS", "").split(",") if x.strip()]
    if origins:
        if "*" in origins:
            raise RuntimeError("HRM_CORS_ORIGINS must contain explicit origins, not a wildcard")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def throttle(request: Request, category: str, subject: str | None = None,
                 *, subject_limit: int = 15, ip_limit: int = 120,
                 window_seconds: int = 900):
        # Do not trust client-controlled X-Forwarded-For. Configure a trusted
        # reverse proxy and independently apply network-level controls.
        ip = request.client.host if request.client else 'unknown'
        with session(path) as connection:
            limiter = RateLimiter(connection, secret)
            ip_ok = limiter.hit(category + ':ip', ip, limit=ip_limit,
                                window_seconds=window_seconds)
            subject_ok = (True if subject is None else limiter.hit(
                category + ':subject', subject, limit=subject_limit,
                window_seconds=window_seconds))
        # Counter increments persist even when returning HTTP 429.
        if not ip_ok or not subject_ok:
            raise HTTPException(status_code=429, detail='Too many requests; try later',
                                headers={'Retry-After': '60'})

    def deliver_mail(connection, kind: str, email: str,
                     organization_code: str, token: str):
        if outbox_key is not None:
            MailQueue(connection, outbox_key).enqueue(
                kind=kind, recipient=email, organization_code=organization_code,
                token=token)
        elif kind == 'verification':
            send_verification(email, token)
        elif kind == 'invitation':
            send_invitation(email, organization_code, token)
        elif kind == 'reset':
            send_password_reset(email, organization_code, token)
        else:
            raise ValueError('Unsupported mail message')

    def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(_AUTH_SCHEME),
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            user_id, session_id = decode_token(credentials.credentials, secret)
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise HTTPException(status_code=401, detail="Invalid or expired session") from None

        with session(path) as connection:
            row = AccountRepository(connection).active_user(user_id)
            active_session = UserSessionRepository(connection).active(
                user_id=user_id, session_id=session_id)
            subscription_active = True
            if row is not None and active_session and enforce:
                try:
                    SubscriptionPolicy(connection).active_plan(row['organization_id'])
                except SubscriptionInactive:
                    subscription_active = False
        if row is None or not active_session:
            raise HTTPException(status_code=401, detail="Session is no longer active")
        return Principal(row["id"], row["organization_id"], row["role"],
                         session_id, subscription_active)

    def licensed_user(user: Principal = Depends(current_user)) -> Principal:
        if not user.subscription_active:
            raise HTTPException(status_code=403, detail='Subscription inactive')
        return user

    def editor(user: Principal = Depends(licensed_user)) -> Principal:
        if user.role not in {"owner", "hr"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    def company_owner(user: Principal = Depends(licensed_user)) -> Principal:
        if user.role != 'owner':
            raise HTTPException(status_code=403, detail='Company owner permission required')
        return user

    def platform_admin(
        credentials: HTTPAuthorizationCredentials | None = Depends(_AUTH_SCHEME),
    ) -> str:
        if not platform_secret:
            raise HTTPException(status_code=503, detail='Platform administration is not configured')
        if credentials is None or credentials.scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail='Platform authentication required')
        try:
            admin_id = decode_platform_token(credentials.credentials, platform_secret)
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise HTTPException(status_code=401, detail='Invalid or expired platform session') from None
        with session(path) as connection:
            row = PlatformRepository(connection).active_admin(admin_id)
        if row is None:
            raise HTTPException(status_code=401, detail='Platform session is no longer active')
        return row['id']

    def employee_row(repository: EmployeeRepository, employee_id: str):
        row = repository.get(employee_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        return row

    def employees(connection: sqlite3.Connection, user: Principal) -> EmployeeRepository:
        return EmployeeRepository(connection, user.organization_id, user.user_id)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post('/api/v1/platform/auth/token')
    def platform_login(data: PlatformLoginRequest, request: Request):
        if not platform_secret:
            raise HTTPException(status_code=503, detail='Platform administration is not configured')
        throttle(request, 'platform-login', data.email)
        with session(path) as connection:
            row = PlatformRepository(connection).login_account(data.email)
        comparison_hash = row['password_hash'] if row else missing_account_hash
        valid = verify_password(data.password, comparison_hash)
        if row is None or not valid:
            raise HTTPException(status_code=401, detail='Invalid credentials')
        return {'access_token': issue_platform_token(row['id'], platform_secret),
                'token_type': 'bearer', 'expires_in': 900}

    @app.get('/api/v1/platform/auth/me')
    def platform_me(admin_id: str = Depends(platform_admin)):
        return {'id': admin_id, 'role': 'platform_owner'}

    @app.get('/api/v1/platform/overview')
    def platform_overview(admin_id: str = Depends(platform_admin)):
        with session(path) as connection:
            return PlatformRepository(connection).overview()

    @app.get('/api/v1/platform/organizations')
    def platform_organizations(
        search: str = Query(default='', max_length=120),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        admin_id: str = Depends(platform_admin),
    ):
        with session(path) as connection:
            return PlatformRepository(connection).list_organizations(search, limit, offset)

    @app.patch('/api/v1/platform/organizations/{organization_id}/status')
    def platform_change_organization_status(
        organization_id: UUID,
        data: PlatformOrganizationStatusChange,
        admin_id: str = Depends(platform_admin),
    ):
        with session(path) as connection:
            outcome = PlatformRepository(connection, admin_id).change_organization_status(
                str(organization_id), data.status,
            )
        if outcome == 'missing':
            raise HTTPException(status_code=404, detail='Organization not found')
        if outcome == 'pending_verification':
            raise HTTPException(status_code=409, detail='Company must verify its owner email first')
        return {'status': data.status, 'changed': outcome == 'updated'}

    @app.get('/api/v1/platform/plans')
    def platform_list_plans(admin_id: str = Depends(platform_admin)):
        with session(path) as connection:
            return {'items': PlatformRepository(connection).list_plans()}

    @app.post('/api/v1/platform/plans', status_code=201)
    def platform_create_plan(data: PlatformPlanInput,
                             admin_id: str = Depends(platform_admin)):
        try:
            with session(path) as connection:
                return PlatformRepository(connection, admin_id).create_plan(**data.model_dump())
        except UNIQUE_ERRORS:
            raise HTTPException(status_code=409, detail='Plan code already exists') from None

    @app.patch('/api/v1/platform/organizations/{organization_id}/subscription')
    def platform_change_subscription(
        organization_id: UUID,
        data: PlatformSubscriptionChange,
        admin_id: str = Depends(platform_admin),
    ):
        try:
            plan_id = str(UUID(data.plan_id))
        except ValueError:
            raise HTTPException(status_code=422, detail='Invalid plan ID') from None
        with session(path) as connection:
            outcome = PlatformRepository(connection, admin_id).change_subscription(
                organization_id=str(organization_id), plan_id=plan_id,
                status=data.status, period_ends_at=data.period_ends_at,
                expected_version=data.expected_version,
            )
        if outcome == 'missing_organization':
            raise HTTPException(status_code=404, detail='Organization not found')
        if outcome == 'invalid_plan':
            raise HTTPException(status_code=422, detail='Plan is unavailable')
        if outcome == 'conflict':
            raise HTTPException(status_code=409, detail='Subscription changed; reload and retry')
        return {'status': data.status, 'changed': True}

    @app.post('/api/v1/organizations/register', status_code=202)
    def register_organization(data: RegisterOrganizationRequest, request: Request):
        throttle(request, 'organization-register', data.owner_email,
                 subject_limit=5, window_seconds=3600)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        hashed_password = hash_password(data.password)
        issued_at = int(time.time())
        try:
            with session(path) as connection:
                OrganizationRegistrationRepository(connection).register(
                    code=data.organization_code,
                    name=data.organization_name,
                    email=data.owner_email,
                    password_hash=hashed_password,
                    token_hash=digest,
                    issued_at=issued_at,
                    expires_at=issued_at + 30 * 60,
                )
                # Delivery failure rolls back this local-development transaction.
                # Production should use a durable asynchronous delivery outbox.
                try:
                    deliver_mail(connection, 'verification', data.owner_email,
                                 data.organization_code, token)
                except Exception:
                    raise HTTPException(
                        status_code=503, detail='Verification delivery unavailable; try again later'
                    ) from None
        except UNIQUE_ERRORS:
            raise HTTPException(status_code=409, detail='Organization code is unavailable') from None
        return {'status': 'pending_email',
                'message': 'Registration received. Verify the owner email to activate the organization.'}

    @app.post('/api/v1/organizations/resend-verification', status_code=202)
    def resend_organization_verification(data: ResendVerificationRequest,
                                         request: Request):
        throttle(request, 'resend-verification',
                 f'{data.organization_code}:{data.owner_email}',
                 subject_limit=5, window_seconds=3600)
        token = secrets.token_urlsafe(32)
        issued_at = int(time.time())
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        with session(path) as connection:
            should_send = OrganizationRegistrationRepository(connection).resend(
                code=data.organization_code,
                email=data.owner_email,
                token_hash=digest,
                issued_at=issued_at,
                expires_at=issued_at + 30 * 60,
            )
            if should_send:
                try:
                    deliver_mail(connection, 'verification', data.owner_email,
                                 data.organization_code, token)
                except Exception:
                    raise HTTPException(status_code=503, detail='Verification delivery unavailable') from None
        # A uniform response helps avoid revealing whether an account exists.
        return {'message': 'If a pending registration matches, a new code will be delivered when eligible.'}

    @app.post('/api/v1/organizations/verify-email')
    def verify_organization_email(data: VerifyEmailRequest, request: Request):
        throttle(request, 'verify-email', ip_limit=500)
        with session(path) as connection:
            verified = OrganizationRegistrationRepository(connection).activate(data.token)
        if not verified:
            raise HTTPException(status_code=400, detail='Invalid or expired verification code')
        return {'status': 'active', 'message': 'Email verified; you can now sign in.'}

    @app.post("/api/v1/auth/token")
    def login(data: LoginRequest, request: Request):
        throttle(request, 'tenant-login', f'{data.organization_code}:{data.email}',
                 ip_limit=600)
        with session(path) as connection:
            row = AccountRepository(connection).login_account(data.organization_code, data.email)
            comparison_hash = row["password_hash"] if row is not None else missing_account_hash
            valid_password = verify_password(data.password, comparison_hash)
            if row is None or not valid_password:
                # Do not reveal whether the account, organization, or password failed.
                raise HTTPException(status_code=401, detail="Invalid credentials")
            if enforce:
                try:
                    SubscriptionPolicy(connection).active_plan(row['organization_id'])
                except SubscriptionInactive:
                    raise HTTPException(status_code=403, detail='Subscription inactive') from None
            refresh = secrets.token_urlsafe(48)
            session_id = UserSessionRepository(connection).create(
                organization_id=row['organization_id'], user_id=row['id'],
                raw_refresh_token=refresh, device_label=data.device_label.strip(),
            )
            return {'access_token': issue_token(row['id'], secret, session_id),
                    'refresh_token': refresh, 'token_type': 'bearer', 'expires_in': 900,
                    'refresh_expires_in': REFRESH_TTL_SECONDS}

    @app.post('/api/v1/auth/refresh')
    def refresh_session(data: RefreshRequest, request: Request):
        throttle(request, 'tenant-refresh', ip_limit=2000)
        new_refresh = secrets.token_urlsafe(48)
        with session(path) as connection:
            repo = UserSessionRepository(connection)
            updated = repo.rotate(data.refresh_token, new_refresh)
            if updated is not None and enforce:
                try:
                    SubscriptionPolicy(connection).active_plan(updated['organization_id'])
                except SubscriptionInactive:
                    raise HTTPException(status_code=403, detail='Subscription inactive') from None
        # If this was a consumed token, the repository revoked the entire
        # device session. Do not roll that database write back on HTTP 401.
        if updated is None:
            raise HTTPException(status_code=401, detail='Refresh token expired or invalid')
        return {'access_token': issue_token(updated['user_id'], secret,
                                            updated['session_id']),
                'refresh_token': new_refresh, 'token_type': 'bearer',
                'expires_in': 900,
                'refresh_expires_in': max(0, updated['expires_at'] - int(time.time()))}

    @app.post('/api/v1/auth/password-resets/request', status_code=202)
    def request_password_reset(data: PasswordResetRequest, request: Request):
        throttle(request, 'password-reset-request',
                 f'{data.organization_code}:{data.email}',
                 subject_limit=6, window_seconds=3600)
        reset_code = secrets.token_urlsafe(48)
        try:
            with session(path) as connection:
                eligible = PasswordResetRepository(connection).request(
                    organization_code=data.organization_code, email=data.email,
                    raw_token=reset_code,
                )
                if eligible:
                    try:
                        deliver_mail(connection, 'reset', data.email,
                                     data.organization_code, reset_code)
                    except Exception:
                        raise _ResetDeliveryFailure() from None
        except _ResetDeliveryFailure:
            logging.getLogger('hrm.delivery').warning(
                'Password recovery delivery failed; transaction rolled back')
        return {'message': 'If the account exists, a recovery code will be sent when eligible.'}

    @app.post('/api/v1/auth/password-resets/confirm')
    def confirm_password_reset(data: PasswordResetConfirm, request: Request):
        throttle(request, 'password-reset-confirm')
        encoded = hash_password(data.new_password)
        with session(path) as connection:
            changed = PasswordResetRepository(connection).confirm(
                raw_token=data.token, password_hash=encoded)
        if not changed:
            raise HTTPException(status_code=400, detail='Invalid or expired reset code')
        return {'message': 'Password updated. All devices were signed out.'}

    @app.get('/api/v1/auth/sessions')
    def list_sessions(user: Principal = Depends(current_user)):
        with session(path) as connection:
            return {'items': UserSessionRepository(connection).list_for_user(
                user.user_id, user.session_id)}

    @app.delete('/api/v1/auth/sessions/{session_id}', status_code=204)
    def revoke_session(session_id: UUID, user: Principal = Depends(current_user)):
        with session(path) as connection:
            changed = UserSessionRepository(connection).revoke(user.user_id, str(session_id))
        if not changed:
            raise HTTPException(status_code=404, detail='Session not found')

    @app.post('/api/v1/auth/logout', status_code=204)
    def logout(user: Principal = Depends(current_user)):
        with session(path) as connection:
            UserSessionRepository(connection).revoke(user.user_id, user.session_id)

    @app.post('/api/v1/auth/logout-all', status_code=204)
    def logout_all(user: Principal = Depends(current_user)):
        with session(path) as connection:
            UserSessionRepository(connection).revoke_all(user.user_id)

    @app.get("/api/v1/auth/me")
    def me(user: Principal = Depends(licensed_user)):
        return {"id": user.user_id, "organization_id": user.organization_id,
                "role": user.role}

    @app.post('/api/v1/organization/invitations', status_code=202)
    def invite_company_user(data: InvitationInput, request: Request,
                            user: Principal = Depends(company_owner)):
        throttle(request, 'company-invite', user.user_id,
                 subject_limit=30, window_seconds=3600)
        invite_code = secrets.token_urlsafe(48)
        with session(path) as connection:
            outcome = InvitationRepository(connection).invite(
                organization_id=user.organization_id, owner_id=user.user_id,
                email=data.email, role=data.role, raw_token=invite_code,
            )
            if outcome == 'existing':
                raise HTTPException(status_code=409, detail='User is already registered')
            if outcome == 'cooldown':
                raise HTTPException(status_code=429, detail='Invitation was sent recently')
            code = connection.execute('SELECT code FROM organizations WHERE id=?',
                                      (user.organization_id,)).fetchone()['code']
            try:
                deliver_mail(connection, 'invitation', data.email, code, invite_code)
            except Exception:
                raise HTTPException(status_code=503, detail='Invitation delivery unavailable') from None
        return {'message': 'Invitation sent. The recipient must set their own password.'}

    @app.get('/api/v1/organization/invitations')
    def list_company_invitations(user: Principal = Depends(company_owner)):
        with session(path) as connection:
            return {'items': InvitationRepository(connection).list_for_company(
                user.organization_id)}

    @app.post('/api/v1/organization/invitations/accept', status_code=201)
    def accept_company_invitation(data: InvitationAccept, request: Request):
        throttle(request, 'invitation-accept', ip_limit=500)
        hashed = hash_password(data.password)
        try:
            with session(path) as connection:
                result = InvitationRepository(connection).accept(data.token, hashed)
        except UNIQUE_ERRORS:
            raise HTTPException(status_code=400, detail='Invitation is invalid or already used') from None
        if result is None:
            raise HTTPException(status_code=400, detail='Invitation is invalid or expired')
        return {'message': 'Account activated. Sign in using your company code and email.'}

    @app.get('/api/v1/organization/users', response_model=OrganizationUserPage)
    def list_company_users(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        user: Principal = Depends(company_owner),
    ):
        with session(path) as connection:
            return OrganizationUserRepository(
                connection, user.organization_id, user.user_id,
            ).list(limit, offset)

    @app.post('/api/v1/organization/users', response_model=OrganizationUserResponse,
              status_code=201, deprecated=True)
    def create_company_user(data: OrganizationUserInput,
                            user: Principal = Depends(company_owner)):
        if not allow_legacy_user_creation:
            raise HTTPException(status_code=410, detail='Use email invitations to add company users')
        encoded = hash_password(data.password)
        try:
            with session(path) as connection:
                result = OrganizationUserRepository(
                    connection, user.organization_id, user.user_id,
                ).create(email=data.email, password_hash=encoded, role=data.role)
        except UNIQUE_ERRORS:
            raise HTTPException(status_code=409, detail='Email already exists in this company') from None
        return dict(result)

    @app.patch('/api/v1/organization/users/{member_id}',
               response_model=OrganizationUserResponse)
    def update_company_user(
        member_id: UUID, data: OrganizationUserPatch,
        user: Principal = Depends(company_owner),
    ):
        payload = data.model_dump(exclude_unset=True)
        version = payload.pop('expected_version')
        if not payload:
            raise HTTPException(status_code=422, detail='Provide a role or active state')
        with session(path) as connection:
            repo = OrganizationUserRepository(
                connection, user.organization_id, user.user_id,
            )
            outcome = repo.patch(str(member_id), payload, version)
            if outcome == 'updated':
                result = dict(repo.get(str(member_id)))
        if outcome == 'not_found':
            raise HTTPException(status_code=404, detail='User not found')
        if outcome == 'protected_owner':
            raise HTTPException(status_code=403, detail='Company owner cannot be changed here')
        if outcome == 'conflict':
            raise HTTPException(status_code=409, detail='User was modified; reload and retry')
        return result

    @app.get("/api/v1/employees", response_model=EmployeePage)
    def list_employees(
        search: str = Query(default="", max_length=120),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        user: Principal = Depends(licensed_user),
    ):
        with session(path) as connection:
            total, rows = employees(connection, user).list(search, limit, offset)
        return {"items": [dict(row) for row in rows], "total": total,
                "limit": limit, "offset": offset}

    @app.get("/api/v1/employees/{employee_id}", response_model=EmployeeResponse)
    def get_employee(employee_id: UUID, user: Principal = Depends(licensed_user)):
        with session(path) as connection:
            return dict(employee_row(employees(connection, user), str(employee_id)))

    @app.post("/api/v1/employees", response_model=EmployeeResponse, status_code=201)
    def create_employee(data: EmployeeInput, user: Principal = Depends(editor)):
        payload = data.model_dump(mode="json")
        try:
            with session(path) as connection:
                if enforce:
                    SubscriptionPolicy(connection).require_seat(user.organization_id)
                repository = employees(connection, user)
                employee_id = repository.create(payload)
                row = employee_row(repository, employee_id)
        except EmployeeSeatLimit:
            raise HTTPException(status_code=409, detail='Employee limit reached for this plan') from None
        except SubscriptionInactive:
            raise HTTPException(status_code=403, detail='Subscription inactive') from None
        except UNIQUE_ERRORS:
            raise HTTPException(status_code=409, detail="Employee code already exists") from None
        return dict(row)

    @app.patch("/api/v1/employees/{employee_id}", response_model=EmployeeResponse)
    def update_employee(
        employee_id: UUID, data: EmployeePatch,
        user: Principal = Depends(editor),
    ):
        fields = data.model_dump(mode="json", exclude_unset=True)
        version = fields.pop("expected_version")
        if not fields:
            raise HTTPException(status_code=422, detail="Provide at least one field to update")
        with session(path) as connection:
            repository = employees(connection, user)
            employee_row(repository, str(employee_id))
            if not repository.update(str(employee_id), fields, version):
                raise HTTPException(status_code=409, detail="Employee was modified; reload and retry")
            return dict(employee_row(repository, str(employee_id)))

    @app.delete("/api/v1/employees/{employee_id}", status_code=204)
    def archive_employee(
        employee_id: UUID,
        expected_version: int = Query(ge=1),
        user: Principal = Depends(editor),
    ):
        with session(path) as connection:
            repository = employees(connection, user)
            employee_row(repository, str(employee_id))
            if not repository.archive(str(employee_id), expected_version):
                raise HTTPException(status_code=409, detail="Employee was modified; reload and retry")

    return app
