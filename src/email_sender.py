"""
Send the digest email via SMTP.

QQ Mail SMTP settings:
  - Host: smtp.qq.com
  - SSL port: 465 (recommended)
  - STARTTLS port: 587 (alternative)
  - Login: full email address
  - Password: SMTP authorization code (NOT the QQ login password)

The auth code is generated at: QQ Mail → Settings → Accounts → IMAP/SMTP service.
Treat it like a password: never commit it to a repo, store it in GitHub Secrets.
"""

import logging
import os
import smtplib
import ssl
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def send_digest_email(
    smtp_user: str,
    smtp_pass: str,
    recipient: str,
    subject: str,
    body: str,
    attachment_path: Optional[str | Path] = None,
    smtp_host: str = "smtp.qq.com",
    smtp_port: int = 465,
    sender_name: str = "Research Digest",
) -> None:
    """Send a single email with optional attachment.

    Raises:
        smtplib.SMTPException: if the SMTP server rejects the message.
    """
    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), smtp_user))
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8").encode()

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path:
        attachment_path = Path(attachment_path)
        if attachment_path.exists():
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            # RFC 2231 encoding for non-ASCII filenames
            filename = attachment_path.name
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=("utf-8", "", filename),
            )
            msg.attach(part)
            logger.info("Attached file: %s (%d bytes)", filename, attachment_path.stat().st_size)
        else:
            logger.warning("Attachment not found: %s", attachment_path)

    logger.info("Connecting to %s:%d as %s", smtp_host, smtp_port, smtp_user)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    logger.info("Email delivered to %s", recipient)


def send_test_email() -> None:
    """Stand-alone smoke test. Reads creds from env vars and sends a tiny email."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("RECIPIENT", smtp_user)

    if not smtp_user or not smtp_pass:
        raise SystemExit("Set SMTP_USER and SMTP_PASS env vars before running this test.")

    send_digest_email(
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        recipient=recipient,
        subject="[Test] Nature & Science Digest SMTP check",
        body=(
            "If you can read this, the SMTP configuration is working.\n\n"
            "You can now safely enable the GitHub Actions schedule."
        ),
        attachment_path=None,
    )
    print("Test email sent. Check your inbox.")


if __name__ == "__main__":
    send_test_email()
