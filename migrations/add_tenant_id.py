#!/usr/bin/env python3
"""
migrations/add_tenant_id.py

One-time migration script to:
  1. Create the tenants table
  2. Create the tenant_configs table
  3. Create the platform_admins table
  4. Add tenant_id column to: leads, lead_updates, exec_targets
  5. Create a default tenant for the existing single-tenant data
  6. Backfill tenant_id = 1 on all existing rows

Run once:
  python -m migrations.add_tenant_id
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from db import engine, SessionLocal, Base

# Import all models so Base.metadata is complete
from models.tenant import Tenant
from models.tenant_config import TenantConfig, set_config
from models.platform_admin import PlatformAdmin
from models.lead import Lead
from models.lead_update import LeadUpdate
from models.exec_target import ExecTarget


def column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() > 0


def run():
    print("[1/6] Creating new tables (tenants, tenant_configs, platform_admins) ...")
    Base.metadata.create_all(engine)
    print("      Done.")

    print("[2/6] Adding tenant_id columns to business tables ...")
    with engine.begin() as conn:
        for table in ("leads", "lead_updates", "exec_targets"):
            if not column_exists(conn, table, "tenant_id"):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1"))
                print(f"      Added tenant_id to '{table}'.")
            else:
                print(f"      '{table}'.tenant_id already exists — skipped.")
    print("      Done.")

    print("[3/6] Creating default tenant for existing single-tenant data ...")
    db = SessionLocal()
    try:
        existing = db.query(Tenant).filter(Tenant.id == 1).first()
        if not existing:
            default_name  = os.getenv("DEFAULT_TENANT_NAME", "Default")
            default_slug  = os.getenv("DEFAULT_TENANT_SLUG", "default")
            admin_pwd     = os.getenv("ADMIN_PASSWORD",    "admin123")
            miniapp_key   = os.getenv("MINIAPP_ACCESS_KEY", "")
            brand_name    = os.getenv("BRAND_NAME",         default_name)
            miniapp_url   = os.getenv("MINIAPP_BASE_URL",   "")

            tenant = Tenant(
                id=1,
                name=default_name,
                slug=default_slug,
                status="active",
                plan="starter",
                admin_password_hash=admin_pwd,
                miniapp_access_key=miniapp_key,
                brand_name=brand_name,
                miniapp_base_url=miniapp_url,
            )
            db.add(tenant)
            db.commit()
            print(f"      Created default tenant id=1 slug='{default_slug}'.")
        else:
            print("      Default tenant already exists — skipped.")

        print("[4/6] Provisioning default config for tenant 1 ...")
        defaults = {
            "stages":               ["Pile", "Footing", "Column", "Slab", "Beam", "Flooring", "Plaster"],
            "materials":            ["RMC", "TMT", "Blocks", "Sand", "Aggregate"],
            "work_statuses":        ["Just Started", "In Progress", "50% Done", "Nearly Complete", "Won", "Lost"],
            "default_monthly_leads":  30,
            "default_conversion_pct": 40.0,
            "default_volume_m3":      500.0,
            "brand_name":             os.getenv("BRAND_NAME", "OLM"),
        }
        for key, value in defaults.items():
            set_config(db, 1, key, value)
        print("      Done.")

        print("[5/6] Backfilling tenant_id = 1 on existing rows ...")
        with engine.begin() as conn:
            for table in ("leads", "lead_updates", "exec_targets"):
                conn.execute(text(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL"))
        print("      Done.")

        print("[6/6] Migration complete ✓")

    finally:
        db.close()


if __name__ == "__main__":
    run()
