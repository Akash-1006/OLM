# models/exec_target.py
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, ForeignKey, UniqueConstraint
from datetime import datetime
from db import Base


class ExecTarget(Base):
    __tablename__ = "exec_targets"

    id              = Column(Integer, primary_key=True)

    # ── Multi-tenancy ──────────────────────────────────────────────────────────
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    sales_exec_id   = Column(BigInteger, nullable=False, index=True)
    sales_exec_name = Column(String(255))

    # Targets (set by tenant admin)
    monthly_leads   = Column(Integer,  default=30)
    conversion_pct  = Column(Float,    default=40.0)
    volume_m3       = Column(Float,    default=500.0)

    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sales_exec_id", name="uq_exec_target_tenant_exec"),
    )
