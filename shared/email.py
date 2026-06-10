"""
Email utility for SecureNet SOC.

Supports sending transactional emails via SMTP or console fallback for development.
Uses HTML templates from shared/email_templates/.
"""

import os
import logging
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@securenet.io")
APP_URL = os.getenv("APP_URL", "http://localhost:5173")

# If SMTP is not configured, log emails to console
USE_CONSOLE = not SMTP_HOST


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def generate_verification_token() -> str:
    """Generate a cryptographically secure verification token."""
    return secrets.token_urlsafe(32)


def generate_invite_token() -> str:
    """Generate a cryptographically secure invitation token."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """
    Send an email via SMTP or log to console in development.
    
    Returns True if sent successfully.
    """
    if USE_CONSOLE:
        logger.info(
            f"[EMAIL] To: {to} | Subject: {subject}\n"
            f"  Body (HTML):\n{html_body[:500]}..."
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_PORT != 25:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to, msg.as_string())

        logger.info(f"Email sent to {to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


# ---------------------------------------------------------------------------
# Template-based emails
# ---------------------------------------------------------------------------

async def send_verification_email(email: str, token: str) -> bool:
    """Send email verification link."""
    verify_url = f"{APP_URL}/verify?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #e0e0e0; padding: 40px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #141b2d; border-radius: 12px; padding: 40px; border: 1px solid #1e2a3a; }}
        .logo {{ color: #00d4ff; font-size: 24px; font-weight: 700; margin-bottom: 20px; }}
        .btn {{ display: inline-block; background: linear-gradient(135deg, #00d4ff, #0090ff); color: white; 
                padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 30px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="logo">🛡️ SecureNet SOC</div>
            <h2>Verify Your Email</h2>
            <p>Welcome to SecureNet! Click the button below to verify your email address and activate your account.</p>
            <a href="{verify_url}" class="btn">Verify Email Address</a>
            <p>Or copy this link: <br><code>{verify_url}</code></p>
            <p class="footer">This link expires in 24 hours. If you didn't create an account, ignore this email.</p>
        </div>
    </body>
    </html>
    """
    return await send_email(email, "Verify your SecureNet account", html)


async def send_invite_email(email: str, token: str, inviter_name: str, tenant_name: str, role: str) -> bool:
    """Send team invitation email."""
    invite_url = f"{APP_URL}/invite?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #e0e0e0; padding: 40px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #141b2d; border-radius: 12px; padding: 40px; border: 1px solid #1e2a3a; }}
        .logo {{ color: #00d4ff; font-size: 24px; font-weight: 700; margin-bottom: 20px; }}
        .btn {{ display: inline-block; background: linear-gradient(135deg, #00d4ff, #0090ff); color: white; 
                padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .role-badge {{ display: inline-block; background: #1e2a3a; padding: 4px 12px; border-radius: 4px; color: #00d4ff; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 30px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="logo">🛡️ SecureNet SOC</div>
            <h2>You've Been Invited!</h2>
            <p><strong>{inviter_name}</strong> has invited you to join <strong>{tenant_name}</strong> on SecureNet SOC as a <span class="role-badge">{role}</span>.</p>
            <a href="{invite_url}" class="btn">Accept Invitation</a>
            <p>Or copy this link: <br><code>{invite_url}</code></p>
            <p class="footer">This invitation expires in 7 days.</p>
        </div>
    </body>
    </html>
    """
    return await send_email(email, f"You're invited to {tenant_name} on SecureNet", html)


async def send_trial_expiring_email(email: str, tenant_name: str, days_remaining: int) -> bool:
    """Send trial expiration warning."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #e0e0e0; padding: 40px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #141b2d; border-radius: 12px; padding: 40px; border: 1px solid #1e2a3a; }}
        .logo {{ color: #00d4ff; font-size: 24px; font-weight: 700; margin-bottom: 20px; }}
        .btn {{ display: inline-block; background: linear-gradient(135deg, #ff6b35, #ff4081); color: white; 
                padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .warning {{ color: #ff6b35; font-weight: 600; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 30px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="logo">🛡️ SecureNet SOC</div>
            <h2>Your Trial is Ending Soon</h2>
            <p class="warning">Your free trial for <strong>{tenant_name}</strong> expires in {days_remaining} day(s).</p>
            <p>Upgrade now to keep your security monitoring active and retain all your alert history.</p>
            <a href="{APP_URL}/app/billing" class="btn">Upgrade Now</a>
            <p class="footer">After your trial ends, you'll be downgraded to the Free plan with limited features.</p>
        </div>
    </body>
    </html>
    """
    return await send_email(email, f"Your SecureNet trial expires in {days_remaining} days", html)
