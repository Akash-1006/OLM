# models/followup.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from db import Base


class FollowUp(Base):
    __tablename__ = "followups"

    id         = Column(Integer, primary_key=True)

    # ── Multi-tenancy ──────────────────────────────────────────────────────────
    tenant_id  = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    lead_id    = Column(Integer, ForeignKey("leads.id"))
    status     = Column(String(50))    # converted / lost / progress
    detail     = Column(String(500))   # order vol / reason / next date
    recorded_at = Column(DateTime, default=datetime.utcnow)
