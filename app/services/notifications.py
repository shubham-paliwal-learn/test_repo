"""Delivery helpers for reminders/reports: e-mail (SMTP or local file) and G-Chat webhook.

Nothing here raises - jobs must never fail because an external channel is not
configured on a demo machine.  When SMTP/webhook credentials are missing the
payload is written to ``logs/outbox.log`` so the delivery is still verifiable.
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from flask import current_app

OUTBOX_PATH = os.path.join(os.path.abspath(os.getcwd()), "logs", "outbox.log")


def _log_outbox(channel: str, payload: dict, delivered: bool, reason: str = "") -> None:
    os.makedirs(os.path.dirname(OUTBOX_PATH), exist_ok=True)
    entry = {
        "channel": channel,
        "delivered": delivered,
        "reason": reason,
        "at": datetime.utcnow().isoformat() + "Z",
        **payload,
    }
    with open(OUTBOX_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def send_mail(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send an e-mail through SMTP; falls back to the local outbox log."""
    app = current_app
    host = app.config.get("MAIL_SERVER")
    recipient = to or app.config.get("ADMIN_EMAIL")
    sender = app.config.get("MAIL_DEFAULT_SENDER") or "tma-noreply@trekking.local"

    if not host or app.config.get("MAIL_SUPPRESS_SEND"):
        _log_outbox("email", {"to": recipient, "subject": subject, "body": text[:400],
                              "html_bytes": len(html) if html else 0},
                   False, "SMTP not configured - recorded in logs/outbox.log")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.attach(MIMEText(text, "plain"))
    if html:
        message.attach(MIMEText(html, "html"))

    try:
        port = int(app.config.get("MAIL_PORT", 587))
        use_tls = bool(app.config.get("MAIL_USE_TLS"))
        use_ssl = bool(app.config.get("MAIL_USE_SSL"))
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                server.starttls()
        username = app.config.get("MAIL_USERNAME")
        password = app.config.get("MAIL_PASSWORD")
        if username:
            server.login(username, password)
        server.sendmail(sender, [recipient], message.as_string())
        server.quit()
        _log_outbox("email", {"to": recipient, "subject": subject}, True, "sent via SMTP")
        return True
    except Exception as exc:  # pragma: no cover - network dependent
        app.logger.warning("Mail delivery failed: %s", exc)
        _log_outbox("email", {"to": recipient, "subject": subject, "body": text[:400]},
                    False, f"SMTP error: {exc}")
        return False


def send_gchat_message(text: str) -> bool:
    """Post a message to a Google Chat webhook (space) if one is configured."""
    url = current_app.config.get("GCHAT_WEBHOOK_URL")
    if not url:
        _log_outbox("gchat", {"message": text[:400]}, False,
                    "GCHAT_WEBHOOK_URL not set - recorded in logs/outbox.log")
        return False
    try:
        response = requests.post(url, json={"text": text}, timeout=10)
        ok = response.status_code < 400
        _log_outbox("gchat", {"status": response.status_code}, ok,
                    "posted to Google Chat webhook" if ok else f"webhook returned {response.status_code}")
        return ok
    except Exception as exc:  # pragma: no cover - network dependent
        _log_outbox("gchat", {"message": text[:200]}, False, f"webhook error: {exc}")
        return False


def send_sms(phone: str, text: str) -> bool:
    """Optional SMS channel (kept simple - uses an HTTP gateway when provided)."""
    gateway = current_app.config.get("SMS_GATEWAY_URL")
    if not gateway or not phone:
        _log_outbox("sms", {"to": phone, "message": text[:200]}, False,
                    "SMS_GATEWAY_URL not set - recorded in logs/outbox.log")
        return False
    try:
        response = requests.post(gateway, data={"to": phone, "text": text}, timeout=10)
        ok = response.status_code < 400
        _log_outbox("sms", {"to": phone}, ok, "posted to SMS gateway")
        return ok
    except Exception as exc:  # pragma: no cover
        _log_outbox("sms", {"to": phone}, False, f"sms error: {exc}")
        return False
