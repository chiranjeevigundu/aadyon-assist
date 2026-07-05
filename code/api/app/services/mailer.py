"""Transactional email — verification + password-reset links.

Backend is chosen by whether a Resend API key is configured: with a key, send via
the Resend HTTP API; without one, log the message to stdout (so dev/CI never send
and nothing breaks when email isn't set up). Kept dependency-light: uses `requests`,
already pinned. Never raises to the caller — a mail failure logs and returns False
so an endpoint can still respond (avoiding account-enumeration timing on reset).
"""
import logging

import requests

from app.core.config import get_settings

log = logging.getLogger("aadyon.mailer")

_RESEND_ENDPOINT = "https://api.resend.com/emails"


def send(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Send one email. Returns True if sent (or logged in dev), False on failure."""
    s = get_settings()
    key = s.resend_api_key
    if not key:
        # No email provider configured — surface the message (incl. the link) at
        # WARNING so it's visible in logs; nothing is actually sent.
        log.warning("[mailer:log-only] to=%s subject=%r\n%s", to, subject, text or html)
        return True
    try:
        resp = requests.post(
            _RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {key}"},
            json={"from": s.mail_from, "to": [to], "subject": subject,
                  "html": html, **({"text": text} if text else {})},
            timeout=10,
        )
        if resp.status_code >= 300:
            log.warning("mailer send failed (%s): %s", resp.status_code, resp.text[:300])
            return False
        return True
    except requests.RequestException as e:
        log.warning("mailer send error: %s", e)
        return False


def send_verification(to: str, link: str) -> bool:
    return send(
        to,
        "Verify your Aadyon Assist email",
        f'<p>Welcome to Aadyon Assist. Confirm your email:</p><p><a href="{link}">Verify email</a></p>',
        f"Welcome to Aadyon Assist. Confirm your email: {link}",
    )


def send_password_reset(to: str, link: str) -> bool:
    return send(
        to,
        "Reset your Aadyon Assist password",
        f'<p>Reset your password:</p><p><a href="{link}">Set a new password</a></p>'
        "<p>If you didn't request this, ignore this email.</p>",
        f"Reset your Aadyon Assist password: {link}\nIf you didn't request this, ignore this email.",
    )
