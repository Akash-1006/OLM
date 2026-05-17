# models/tenant_config.py
"""
Key-value config store per tenant.

Examples of keys:
  stages            → JSON list  ["Pile", "Footing", "Slab", ...]
  materials         → JSON list  ["RMC", "TMT", ...]
  work_statuses     → JSON list  ["Just Started", "In Progress", "Completed", ...]
  default_monthly_leads   → int 30
  default_conversion_pct  → float 40.0
  default_volume_m3       → float 500.0
  brand_name        → str  "Titans"
  brand_color       → str  "#01696f"
  quote_template_url→ str
"""
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from db import Base
from typing import Any, Optional


class TenantConfig(Base):
    __tablename__   = "tenant_configs"
    __table_args__  = (UniqueConstraint("tenant_id", "key"),)

    id          = Column(Integer, primary_key=True, index=True)
    tenant_id   = Column(Integer, nullable=False, index=True)
    key         = Column(String(128), nullable=False)
    value_json  = Column(Text, nullable=True)   # JSON-encoded value
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<TenantConfig tenant={self.tenant_id} key={self.key!r}>"


def get_config(db: Session, tenant_id: int, key: str, default: Any = None) -> Any:
    row = db.query(TenantConfig).filter(
        TenantConfig.tenant_id == tenant_id,
        TenantConfig.key == key,
    ).first()
    if row is None or row.value_json is None:
        return default
    try:
        return json.loads(row.value_json)
    except (TypeError, ValueError):
        return default


def set_config(db: Session, tenant_id: int, key: str, value: Any) -> None:
    row = db.query(TenantConfig).filter(
        TenantConfig.tenant_id == tenant_id,
        TenantConfig.key == key,
    ).first()
    encoded = json.dumps(value)
    if row:
        row.value_json = encoded
    else:
        row = TenantConfig(tenant_id=tenant_id, key=key, value_json=encoded)
        db.add(row)
    db.commit()
