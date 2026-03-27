# models/exec_target.py
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, UniqueConstraint
from datetime import datetime
from db import Base

class ExecTarget(Base):
    __tablename__ = "exec_targets"

    id              = Column(Integer, primary_key=True)
    sales_exec_id   = Column(BigInteger, nullable=False, index=True)
    sales_exec_name = Column(String(255))

    # Targets (admin-set)
    monthly_leads   = Column(Integer,  default=30)    # leads/month
    conversion_pct  = Column(Float,    default=40.0)  # % conversion rate target
    volume_m3       = Column(Float,    default=500.0) # m³ volume target/month

    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("sales_exec_id", name="uq_exec_target_exec_id"),
    )