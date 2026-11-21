"""Strict boundaries for employee API input and output."""

from datetime import date
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _email(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if not value:
        return None
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid email address")
    return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    device_label: str = Field(default='HRM client', min_length=2, max_length=60)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError("Email is required")
        return normalized


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    refresh_token: str = Field(min_length=32, max_length=256,
                               pattern=r'^[A-Za-z0-9_-]+$')


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    role: Literal['hr', 'viewer']

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError('Email is required')
        return normalized


class InvitationAccept(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    token: str = Field(min_length=32, max_length=256,
                       pattern=r'^[A-Za-z0-9_-]+$')
    password: str = Field(min_length=12, max_length=1024)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    organization_code: str = Field(min_length=2, max_length=40,
                                   pattern=r'^[a-z0-9_-]+$')
    email: str = Field(min_length=3, max_length=254)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError('Email is required')
        return normalized


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    token: str = Field(min_length=32, max_length=256,
                       pattern=r'^[A-Za-z0-9_-]+$')
    new_password: str = Field(min_length=12, max_length=1024)


class RegisterOrganizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    organization_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    organization_name: str = Field(min_length=2, max_length=120)
    owner_email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("owner_email")
    @classmethod
    def normalize_owner_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError("Email is required")
        return normalized


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    organization_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    owner_email: str = Field(min_length=3, max_length=254)

    @field_validator('owner_email')
    @classmethod
    def normalize_owner_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError('Email is required')
        return normalized


class PlatformLoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError('Email is required')
        return normalized


class PlatformPlanInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    code: str = Field(min_length=2, max_length=40, pattern=r'^[a-z0-9_-]+$')
    name: str = Field(min_length=2, max_length=100)
    price_halalas: int = Field(ge=0, le=100_000_000)
    max_employees: int = Field(ge=1, le=1_000_000)


class PlatformOrganizationStatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['active', 'suspended']


class PlatformSubscriptionChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_id: str = Field(min_length=36, max_length=36)
    status: Literal['trialing', 'active', 'past_due', 'canceled']
    expected_version: int = Field(ge=1)
    period_ends_at: int = Field(ge=1_700_000_000, le=4_102_444_800)


class OrganizationUserInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)
    role: Literal['hr', 'viewer']

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = _email(value)
        if normalized is None:
            raise ValueError('Email is required')
        return normalized


class OrganizationUserPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    role: Literal['hr', 'viewer'] | None = None
    is_active: bool | None = None

    @field_validator('role', 'is_active')
    @classmethod
    def validate_nullable_fields(cls, value):
        if value is None:
            raise ValueError('This field cannot be null')
        return value


class OrganizationUserResponse(BaseModel):
    id: str
    email: str
    role: Literal['owner', 'hr', 'viewer']
    is_active: bool
    version: int
    created_at: str


class OrganizationUserPage(BaseModel):
    items: list[OrganizationUserResponse]
    total: int
    limit: int
    offset: int


class EmployeeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    employee_code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    full_name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    hire_date: date
    status: Literal["active", "inactive"] = "active"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _email(value)


class EmployeePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    job_title: str | None = Field(default=None, min_length=2, max_length=100)
    department: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    hire_date: date | None = None
    status: Literal["active", "inactive"] | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _email(value)

    @field_validator("full_name", "job_title", "department", "hire_date", "status")
    @classmethod
    def validate_non_nullable(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class EmployeeResponse(BaseModel):
    id: str
    employee_code: str
    full_name: str
    job_title: str
    department: str
    email: str | None
    phone: str | None
    hire_date: date
    status: Literal["active", "inactive"]
    version: int
    created_at: str
    updated_at: str


class EmployeePage(BaseModel):
    items: list[EmployeeResponse]
    total: int
    limit: int
    offset: int
