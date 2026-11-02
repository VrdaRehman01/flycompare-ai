"""Outgoing email over SMTP (e.g. Gmail with an App Password, or any SMTP provider).

Delivery is synchronous and reports failure honestly: callers get an exception and
tell the user the email could not be sent, rather than pretending it was. Message
contents (which carry sign-in codes) and credentials are never logged.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailNotConfigured(Exception):
    """No SMTP server is configured."""


class EmailDeliveryFailed(Exception):
    """The SMTP server could not be reached or refused the message."""


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_username and s.smtp_password)


def send(to: str, subject: str, text: str, html: str | None = None) -> None:
    settings = get_settings()
    if not is_configured():
        raise EmailNotConfigured("Email is not configured on this server.")
    sender = settings.email_from or settings.smtp_username
    message = EmailMessage()
    message["From"] = formataddr((settings.email_from_name, sender))
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    context = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.email_timeout_seconds, context=context) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.email_timeout_seconds) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Log the failure class only: never the message (it holds a code) or credentials.
        logger.warning("Email delivery failed: %s", exc.__class__.__name__)
        raise EmailDeliveryFailed("The email could not be sent.") from exc
