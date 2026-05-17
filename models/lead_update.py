# models/lead_update.py
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey
from datetime import datetime
from db import Base


class LeadUpdate(Base):
    __tablename__ = "lead_updates"

    id              = Column(Integer, primary_key=True)

    # ── Multi-tenancy ──────────────────────────────────────────────────────────
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    lead_id         = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    sales_exec_id   = Column(BigInteger)
    sales_exec_name = Column(String(255))

    company_name = Column(String(255))
    client_name  = Column(String(255))
    client_phone = Column(String(20))
    site_status  = Column(String(50))
    stage        = Column(String(50))
    material     = Column(String(50))
    grade        = Column(String(20))
    quantity     = Column(String(50))
    remarks      = Column(Text)

    updated_at   = Column(DateTime, default=datetime.utcnow)
