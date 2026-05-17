# models/lead.py
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, Text, ForeignKey
from datetime import datetime
from db import Base


class Lead(Base):
    __tablename__ = "leads"

    id            = Column(Integer, primary_key=True)

    # ── Multi-tenancy ──────────────────────────────────────────────────────────
    tenant_id     = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # ── Lead fields ───────────────────────────────────────────────────────────
    company_name  = Column(String(255))
    client_name   = Column(String(255))           # contact person
    client_phone  = Column(String(20))
    site_status   = Column(String(50))            # work status (config-driven per tenant)
    stage         = Column(String(50))            # config-driven per tenant
    material      = Column(String(50))            # config-driven per tenant
    grade         = Column(String(20))            # Sq Ft (optional)
    quantity      = Column(String(50))            # entered as string to support units
    remarks       = Column(Text)                  # optional notes
    photo_paths   = Column(Text)                  # comma-separated file paths on disk
    latitude      = Column(Float, nullable=True)
    longitude     = Column(Float, nullable=True)
    location      = Column(String(255))           # "lat,lng" string for display
    sales_exec_id   = Column(BigInteger)            # Telegram user ID
    sales_exec_name = Column(String(255))           # Telegram display name (saved at submit time)
    last_followup_at    = Column(DateTime, nullable=True)
    next_followup_date  = Column(DateTime, nullable=True)
    last_user_update_at = Column(DateTime, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)
