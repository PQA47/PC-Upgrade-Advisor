import os
import smtplib
import ssl
from email.message import EmailMessage


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_username).strip()

    if not smtp_username or not smtp_password:
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env."
        )

    if not smtp_from:
        raise RuntimeError("SMTP_FROM is empty.")

    message = EmailMessage()
    message["Subject"] = "PC Upgrade Advisor - Password reset"
    message["From"] = smtp_from
    message["To"] = recipient
    message.set_content(
        f"""Hello,

We received a request to reset your PC Upgrade Advisor password.

Open this link to choose a new password:

{reset_url}

This link expires in 30 minutes and can only be used once.

If you did not request this, you can ignore this email.

PC Upgrade Advisor
"""
    )

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp_username, smtp_password)
        server.send_message(message)
