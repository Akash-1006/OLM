# models/exec_target.py
from sqlalchemy import Column, Integer, Float, String, UniqueConstraint
from db import Base


class ExecTarget(Base):
    __tablename__   = "exec_targets"
    __table_args__  = (UniqueConstraint("tenant_id", "sales_exec_id"),)

    id              = Column(Integer, primary_key=True)
    tenant_id       = Column(Integer, nullable=False, default=1, index=True)
    sales_exec_id   = Column(Integer, nullable=False, index=True)
    monthly_leads   = Column(Integer, default=30)
    conversion_pct  = Column(Float,   default=40.0)
    volume_m3       = Column(Float,   default=500.0)

    def __repr__(self):
        return f"<ExecTarget tenant={self.tenant_id} exec={self.sales_exec_id}>"
