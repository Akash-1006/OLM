# models/tenant.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from db import Base


class Tenant(Base):
    """One row = one paying customer / business deploying OLM."""
    __tablename__ = "tenants"

    id                  = Column(Integer, primary_key=True)
    name                = Column(String(255), nullable=False)          # e.g. "Titans Concrete"
    slug                = Column(String(100), unique=True, nullable=False)  # e.g. "titans" → subdomain
    plan                = Column(String(50),  default="free")           # free / pro / enterprise
    status              = Column(String(20),  default="active")         # active / suspended / trial

    # Telegram bot credentials for this tenant
    telegram_token      = Column(String(255), nullable=True)
    webhook_url         = Column(String(512), nullable=True)
    miniapp_base_url    = Column(String(512), nullable=True)

    # Auth
    admin_password_hash = Column(String(255), nullable=True)  # bcrypt hash
    miniapp_access_key  = Column(String(255), nullable=True)

    # Telegram chat_id of the org owner for daily digests
    digest_owner_chat_id = Column(String(50), nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
