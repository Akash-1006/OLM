# models/platform_admin.py
"""
Platform-level admin accounts (master admin panel).
Separate from tenant users.
"""
import os
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from db import Base


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id          = Column(Integer, primary_key=True)
    username    = Column(String(64), unique=True, nullable=False)
    password    = Column(String(255), nullable=False)  # bcrypt in production
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


def verify_platform_admin(username: str, password: str, db: Session) -> bool:
    """
    Verify master admin credentials.
    Falls back to MASTER_ADMIN_PASSWORD env var for simple single-admin setups.
    """
    master_key = os.getenv("MASTER_ADMIN_PASSWORD", "")
    if master_key and password == master_key:
        return True
    admin = db.query(PlatformAdmin).filter(
        PlatformAdmin.username == username,
        PlatformAdmin.is_active == True,
    ).first()
    return admin is not None and admin.password == password
