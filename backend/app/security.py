"""Authenticated session tokens and versioned password hashes."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import os
import uuid

import jwt


_SCRYPT_N = 1 << 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_ISSUER = "hrm-core"
_AUDIENCE = "hrm-core-client"
_PLATFORM_ISSUER = 'hrm-core-platform'
_PLATFORM_AUDIENCE = 'hrm-core-platform-console'


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    salt = os.urandom(16)
    result = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N,
        r=_SCRYPT_R, p=_SCRYPT_P, dklen=32, maxmem=_SCRYPT_MAXMEM,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_encode(salt)}${_encode(result)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        cost, block, parallel = int(n), int(r), int(p)
        # Never accept unbounded work factors read from the database.
        if (cost, block, parallel) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        found = hashlib.scrypt(
            password.encode("utf-8"), salt=_decode(salt), n=cost,
            r=block, p=parallel, dklen=32, maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(found, _decode(expected))
    except (ValueError, TypeError, UnicodeError):
        return False


def issue_token(user_id: str, secret: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id, "sid": session_id, "iss": _ISSUER, "aud": _AUDIENCE,
            "iat": now, "nbf": now, "exp": now + timedelta(minutes=15),
            "jti": str(uuid.uuid4()),
        },
        secret,
        algorithm="HS256",
    )


def decode_token(token: str, secret: str) -> tuple[str, str]:
    claims = jwt.decode(
        token, secret, algorithms=["HS256"],
        issuer=_ISSUER, audience=_AUDIENCE,
        options={"require": ["sub", "sid", "exp", "iat", "iss", "aud", "nbf"]},
    )
    return str(uuid.UUID(claims["sub"])), str(uuid.UUID(claims["sid"]))


def issue_platform_token(admin_id: str, platform_secret: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            'sub': admin_id, 'iss': _PLATFORM_ISSUER, 'aud': _PLATFORM_AUDIENCE,
            'iat': now, 'nbf': now, 'exp': now + timedelta(minutes=15),
            'jti': str(uuid.uuid4()), 'scope': 'platform_owner',
        },
        platform_secret, algorithm='HS256',
    )


def decode_platform_token(token: str, platform_secret: str) -> str:
    claims = jwt.decode(
        token, platform_secret, algorithms=['HS256'],
        issuer=_PLATFORM_ISSUER, audience=_PLATFORM_AUDIENCE,
        options={'require': ['sub', 'exp', 'iat', 'iss', 'aud', 'nbf', 'scope']},
    )
    if claims['scope'] != 'platform_owner':
        raise ValueError('Invalid platform scope')
    return str(uuid.UUID(claims['sub']))
