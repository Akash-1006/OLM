# models/tenant.py
"""
Tenant — one row per customer/business that uses the platform.

Every other business-data table (Lead, ExecTarget, LeadUpdate …) carries
a tenant_id FK pointing here.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id                  = Column(Integer, primary_key=True, index=True)
    name                = Column(String(128), nullable=False)      # display name
    slug                = Column(String(64),  unique=True, index=True, nullable=False)  # subdomain
    status              = Column(String(32),  default="active")    # active | suspended | trial
    plan                = Column(String(32),  default="starter")   # starter | pro | enterprise

    # Auth
    admin_password_hash = Column(String(255), nullable=True)   # bcrypt later; plain for now
    miniapp_access_key  = Column(String(128), nullable=True)

    # Telegram
    telegram_bot_token  = Column(String(255), nullable=True)   # optional per-tenant bot
    telegram_group_id   = Column(String(64),  nullable=True)

    # Branding
    brand_name          = Column(String(128), nullable=True)
    brand_logo_url      = Column(Text,        nullable=True)
    brand_color         = Column(String(16),  nullable=True)

    # URLs
    miniapp_base_url    = Column(String(255), nullable=True)
    webhook_url         = Column(String(255), nullable=True)

    # Timestamps
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Tenant id={self.id} slug={self.slug!r} status={self.status!r}>"
