"""Verification-token delivery for local development and optional SMTP SSL.

The development outbox is intentionally local-only and contains plaintext
secrets. Never commit, sync or deploy it. Production SMTP delivery and an
asynchronous transactional outbox require further security review.
"""

import os
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
from collections.abc import Callable

from .postgres_adapter import is_postgres_dsn


VerificationSender = Callable[[str, str], None]
InvitationSender = Callable[[str, str, str], None]
PasswordResetSender = Callable[[str, str, str], None]


def configured_verification_sender(database_path: str) -> VerificationSender:
    host = os.getenv('HRM_SMTP_HOST', '').strip()
    if host:
        username = os.getenv('HRM_SMTP_USERNAME', '').strip()
        password = os.getenv('HRM_SMTP_PASSWORD', '')
        from_address = os.getenv('HRM_SMTP_FROM', '').strip()
        port = int(os.getenv('HRM_SMTP_PORT', '465'))
        if not username or not password or not from_address or not 1 <= port <= 65535:
            raise RuntimeError('SMTP SSL requires valid username, password, from address and port')

        def send_email(email: str, token: str) -> None:
            message = EmailMessage()
            message['Subject'] = 'Verify your HRM Core organization email'
            message['From'] = from_address
            message['To'] = email
            message.set_content(
                'Use this one-time verification code in HRM Core. '
                'It expires in 30 minutes.\n\n' + token + '\n\n'
                'If you did not register, ignore this message.\n'
            )
            with smtplib.SMTP_SSL(host, port, timeout=12,
                                  context=ssl.create_default_context()) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)

        return send_email

    # The backend cannot start in production, so this outbox only exists in
    # the explicitly non-production development/test environment.
    outbox_root = (Path('./data').resolve() if is_postgres_dsn(database_path)
                   else Path(database_path).resolve().parent)
    outbox = outbox_root / 'verification-outbox.txt'

    def write_local_outbox(email: str, token: str) -> None:
        outbox.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(outbox, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(fd, 'a', encoding='utf-8') as output:
                output.write(f'{email}\t{token}\n')
        except BaseException:
            # fdopen owns and closes the descriptor even if write fails.
            raise

    return write_local_outbox


def configured_invitation_sender(database_path: str) -> InvitationSender:
    """Deliver a 48-hour single-use invitation, never via an API response."""
    host = os.getenv('HRM_SMTP_HOST', '').strip()
    if host:
        username = os.getenv('HRM_SMTP_USERNAME', '').strip()
        password = os.getenv('HRM_SMTP_PASSWORD', '')
        from_address = os.getenv('HRM_SMTP_FROM', '').strip()
        port = int(os.getenv('HRM_SMTP_PORT', '465'))
        if not username or not password or not from_address or not 1 <= port <= 65535:
            raise RuntimeError('SMTP SSL requires valid credentials and sender')

        def send_invitation(email: str, organization_code: str, token: str) -> None:
            message = EmailMessage()
            message['Subject'] = 'Your HRM Core company invitation'
            message['From'] = from_address
            message['To'] = email
            message.set_content(
                'You have been invited to HRM Core. If you recognize this invitation, '
                'open the app and select Accept invitation.\n'
                f'Company code: {organization_code}\n'
                f'One-time invitation code: {token}\n'
                'Expires in 48 hours. Set your own password; do not share the code.\n'
                'If unexpected, ignore this message.\n'
            )
            with smtplib.SMTP_SSL(host, port, timeout=12,
                                  context=ssl.create_default_context()) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)

        return send_invitation

    outbox_root = (Path('./data').resolve() if is_postgres_dsn(database_path)
                   else Path(database_path).resolve().parent)
    outbox = outbox_root / 'invitation-outbox.txt'

    def write_local_invitation(email: str, organization_code: str, token: str) -> None:
        outbox.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(outbox, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a', encoding='utf-8') as output:
            output.write(f'{email}\t{organization_code}\t{token}\n')

    return write_local_invitation


def configured_password_reset_sender(database_path: str) -> PasswordResetSender:
    host = os.getenv('HRM_SMTP_HOST', '').strip()
    if host:
        username = os.getenv('HRM_SMTP_USERNAME', '').strip()
        password = os.getenv('HRM_SMTP_PASSWORD', '')
        from_address = os.getenv('HRM_SMTP_FROM', '').strip()
        port = int(os.getenv('HRM_SMTP_PORT', '465'))
        if not username or not password or not from_address or not 1 <= port <= 65535:
            raise RuntimeError('SMTP SSL requires valid credentials and sender')

        def send_reset(email: str, organization_code: str, token: str) -> None:
            message = EmailMessage()
            message['Subject'] = 'Reset your HRM Core password'
            message['From'] = from_address
            message['To'] = email
            message.set_content(
                'A password reset was requested for HRM Core. '
                'Open the app and select Reset password.\n'
                f'Company code: {organization_code}\n'
                f'One-time reset code: {token}\n'
                'Expires in 30 minutes. If unexpected, ignore this message.\n'
            )
            with smtplib.SMTP_SSL(host, port, timeout=12,
                                  context=ssl.create_default_context()) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)

        return send_reset

    outbox_root = (Path('./data').resolve() if is_postgres_dsn(database_path)
                   else Path(database_path).resolve().parent)
    outbox = outbox_root / 'reset-outbox.txt'

    def write_local_reset(email: str, organization_code: str, token: str) -> None:
        outbox.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(outbox, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a', encoding='utf-8') as output:
            output.write(f'{email}\t{organization_code}\t{token}\n')

    return write_local_reset
