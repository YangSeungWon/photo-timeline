import secrets
import logging
from typing import Optional
from fastapi import HTTPException
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from jinja2 import Template

from .config import settings
from .database import engine
from sqlmodel import Session, select
from ..models.user import User


# Email configuration
email_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USER,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM or settings.MAIL_USER,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_HOST,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_SECURE,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

fastmail = FastMail(email_config)

logger = logging.getLogger(__name__)


# Email templates
EMAIL_VERIFICATION_TEMPLATE = """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2563eb; text-align: center; margin-bottom: 30px;">
            📸 Photo Timeline
        </h1>
        
        <h2 style="color: #1f2937; margin-bottom: 20px;">
            Verify Your Email Address
        </h2>
        
        <p style="color: #4b5563; font-size: 16px; line-height: 1.6;">
            Hi {{ display_name }},
        </p>
        
        <p style="color: #4b5563; font-size: 16px; line-height: 1.6;">
            Welcome to Photo Timeline! Please click the button below to verify your email address and activate your account.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ verification_url }}" 
               style="background-color: #2563eb; color: white; padding: 15px 30px; 
                      text-decoration: none; border-radius: 5px; font-weight: bold; 
                      display: inline-block;">
                Verify Email Address
            </a>
        </div>
        
        <p style="color: #6b7280; font-size: 14px; line-height: 1.6;">
            If you can't click the button, copy and paste this link into your browser:<br>
            <a href="{{ verification_url }}" style="color: #2563eb; word-break: break-all;">
                {{ verification_url }}
            </a>
        </p>
        
        <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin-top: 30px;">
            This verification link will expire in 24 hours. If you didn't create an account with Photo Timeline, 
            you can safely ignore this email.
        </p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
            © {{ current_year }} Photo Timeline. All rights reserved.
        </p>
    </div>
</body>
</html>
"""


def generate_verification_token() -> str:
    """Generate a secure verification token."""
    return secrets.token_urlsafe(32)


def get_verification_email_template(display_name: str, verification_token: str) -> str:
    """Generate HTML email template for verification."""
    verification_url = f"{settings.FRONTEND_URL or 'http://localhost:3067'}/verify-email?token={verification_token}"
    
    template = Template(EMAIL_VERIFICATION_TEMPLATE)
    return template.render(
        display_name=display_name,
        verification_url=verification_url,
        current_year=2025
    )


async def send_verification_email(user_email: str, display_name: str, verification_token: str):
    """Send email verification email to user."""
    try:
        html_template = get_verification_email_template(display_name, verification_token)
        
        message = MessageSchema(
            subject="Verify your Photo Timeline account",
            recipients=[user_email],
            body=html_template,
            subtype=MessageType.html
        )
        
        await fastmail.send_message(message)
        logger.info(f"Verification email sent successfully to {user_email}")
        
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")


def store_verification_token(user_id: str, token: str, db: Session) -> None:
    """Store verification token in user record."""
    user = db.exec(select(User).where(User.id == user_id)).first()
    if user:
        user.email_verification_token = token
        user.email_verification_expires = None  # We'll add expiry field later
        db.add(user)
        db.commit()


def verify_email_token(token: str, db: Session) -> Optional[User]:
    """Verify email token and activate user account."""
    user = db.exec(select(User).where(User.email_verification_token == token)).first()
    if user and not user.email_verified:
        user.email_verified = True
        user.email_verification_token = None
        user.is_active = True
        db.add(user)
        db.commit()
        return user
    return None 