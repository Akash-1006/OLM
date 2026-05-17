# models/tenant_config.py
"""
Flexible key-value config store for each tenant.
All structured config (stages, materials, follow-up rules, digest time, etc.)
is stored here as JSON strings so no schema migrations are needed to add
new config options.

Usage:
    from models.tenant_config import TenantConfig, get_config, set_config
    stages = get_config(session, tenant_id, "stages", default=["Foundation", "Ready"])
    set_config(session, tenant_id, "stages", ["Foundation", "Brick", "Plastering", "Ready"])
"""
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime
from db import Base


class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    id         = Column(Integer, primary_key=True)
    tenant_id  = Column(Integer, nullable=False, index=True)
    key        = Column(String(100), nullable=False)
    value      = Column(Text, nullable=True)   # JSON-serialised value
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_tenant_config_key"),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_config(session, tenant_id: int, key: str, default=None):
    """Return the parsed value for (tenant_id, key), or default if not set."""
    row = (
        session.query(TenantConfig)
        .filter(
            TenantConfig.tenant_id == tenant_id,
            TenantConfig.key == key,
        )
        .first()
    )
    if row is None or row.value is None:
        return default
    try:
        return json.loads(row.value)
    except (ValueError, TypeError):
        return row.value  # return raw string if not valid JSON


def set_config(session, tenant_id: int, key: str, value) -> None:
    """Upsert a config value for (tenant_id, key)."""
    row = (
        session.query(TenantConfig)
        .filter(
            TenantConfig.tenant_id == tenant_id,
            TenantConfig.key == key,
        )
        .first()
    )
    if row is None:
        row = TenantConfig(tenant_id=tenant_id, key=key)
        session.add(row)
    row.value = json.dumps(value)


def seed_default_config(session, tenant_id: int) -> None:
    """
    Seed a brand-new tenant with sensible defaults.
    Call this once right after creating a Tenant row.
    """
    defaults = {
        "stages": [
            "Pile", "Footing", "Slab", "Flooring",
            "Column", "Brick", "Plastering", "Ready",
        ],
        "materials": ["White", "Colour", "Aluminium"],
        "work_statuses": [
            "Visited", "Quoted", "Won", "Lost",
            "Negotiation in Progress",
        ],
        # stage → follow-up interval in days
        "followup_rules": {
            "Pile":       1,
            "Footing":    3,
            "Slab":       3,
            "Flooring":   4,
            "Column":     7,
            "Brick":      5,
            "Plastering": 5,
            "Ready":      2,
        },
        # Default exec targets
        "default_monthly_leads":  30,
        "default_conversion_pct": 40.0,
        "default_volume_m3":      500.0,
        # Daily digest time in IST (HH:MM)
        "digest_time_ist": "20:00",
        # Brand name shown in exports and bot messages
        "brand_name": "OLM",
    }
    for key, value in defaults.items():
        # Only seed if not already set (safe to call multiple times)
        existing = (
            session.query(TenantConfig)
            .filter(
                TenantConfig.tenant_id == tenant_id,
                TenantConfig.key == key,
            )
            .first()
        )
        if existing is None:
            set_config(session, tenant_id, key, value)
