# models/platform_admin.py
"""
Platform-level super-admins (i.e. YOU, the SaaS operator).
These users can manage all tenants via the master admin panel.
"""
import hashlib
import os
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from db import Base


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id             = Column(Integer, primary_key=True)
    username       = Column(String(100), unique=True, nullable=False)
    password_hash  = Column(String(255), nullable=False)  # SHA-256 hex (upgrade to bcrypt later)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    last_login_at  = Column(DateTime, nullable=True)


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Simple SHA-256 hash (replace with bcrypt in production)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_platform_admin(session, username: str, password: str):
    """
    Return the PlatformAdmin row if credentials are correct, else None.
    Also updates last_login_at on success.
    """
    admin = (
        session.query(PlatformAdmin)
        .filter(
            PlatformAdmin.username == username,
            PlatformAdmin.is_active == True,
        )
        .first()
    )
    if admin and admin.password_hash == _hash_password(password):
        admin.last_login_at = datetime.utcnow()
        session.commit()
        return admin
    return None


def create_platform_admin(session, username: str, password: str) -> "PlatformAdmin":
    """Create a new platform admin. Raises ValueError if username already exists."""
    existing = session.query(PlatformAdmin).filter_by(username=username).first()
    if existing:
        raise ValueError(f"Platform admin '{username}' already exists.")
    admin = PlatformAdmin(
        username=username,
        password_hash=_hash_password(password),
    )
    session.add(admin)
    session.commit()
    return admin
