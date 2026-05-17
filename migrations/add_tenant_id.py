#!/usr/bin/env python3
"""
migrations/add_tenant_id.py

One-time migration script to:
  1. Create the tenants, tenant_configs, platform_admins tables
  2. Add tenant_id column to: leads, lead_updates, exec_targets
  3. Create a default tenant for the existing single-tenant data
  4. Seed default config for tenant 1
  5. Backfill tenant_id = 1 on all existing rows

Works with both SQLite (dev) and PostgreSQL (prod).

Run once:
  python migrations/add_tenant_id.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect as sa_inspect
from db import engine, SessionLocal, Base

# Import all models so Base.metadata is populated
from models.tenant import Tenant
from models.tenant_config import TenantConfig, set_config, seed_default_config
from models.platform_admin import PlatformAdmin
from models.lead import Lead
from models.lead_update import LeadUpdate
from models.exec_target import ExecTarget


def column_exists(table: str, column: str) -> bool:
    """Check if a column exists using SQLAlchemy's cross-DB inspector."""
    inspector = sa_inspect(engine)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def table_exists(table: str) -> bool:
    inspector = sa_inspect(engine)
    return table in inspector.get_table_names()


def run():
    print("\n=== OLM SaaS Migration ===\n")

    # ── Step 1: Create new tables ──────────────────────────────────────────────
    print("[1/5] Creating new tables (tenants, tenant_configs, platform_admins) ...")
    Base.metadata.create_all(engine)
    print("      Done.")

    # ── Step 2: Add tenant_id columns ─────────────────────────────────────────
    print("[2/5] Adding tenant_id columns to business tables ...")
    with engine.begin() as conn:
        for table in ("leads", "lead_updates", "exec_targets"):
            if not table_exists(table):
                print(f"      Table '{table}' does not exist — skipped.")
                continue
            if not column_exists(table, "tenant_id"):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT 1"))
                print(f"      Added tenant_id to '{table}'.")
            else:
                print(f"      '{table}'.tenant_id already exists — skipped.")
    print("      Done.")

    # ── Step 3: Create default tenant ─────────────────────────────────────────
    print("[3/5] Creating default tenant for existing data ...")
    db = SessionLocal()
    try:
        existing = db.query(Tenant).filter(Tenant.id == 1).first()
        if not existing:
            default_name = os.getenv("DEFAULT_TENANT_NAME", "Default")
            default_slug = os.getenv("DEFAULT_TENANT_SLUG", "default")
            admin_pwd    = os.getenv("ADMIN_PASSWORD",      "admin123")
            miniapp_key  = os.getenv("MINIAPP_ACCESS_KEY",  "")
            miniapp_url  = os.getenv("MINIAPP_BASE_URL",    "")

            tenant = Tenant(
                id=1,
                name=default_name,
                slug=default_slug,
                status="active",
                plan="starter",
                admin_password_hash=admin_pwd,
                miniapp_access_key=miniapp_key,
                miniapp_base_url=miniapp_url,
            )
            db.add(tenant)
            db.commit()
            print(f"      Created default tenant id=1 slug='{default_slug}'.")
        else:
            print("      Default tenant already exists — skipped.")

        # ── Step 4: Seed config ────────────────────────────────────────────────
        print("[4/5] Seeding default config for tenant 1 ...")
        seed_default_config(db, 1)
        db.commit()
        print("      Done.")

        # ── Step 5: Backfill tenant_id ─────────────────────────────────────────
        print("[5/5] Backfilling tenant_id = 1 on all existing rows ...")
        with engine.begin() as conn:
            for table in ("leads", "lead_updates", "exec_targets"):
                if table_exists(table):
                    conn.execute(text(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL"))
        print("      Done.")

        print("\n=== Migration complete ✓ ===")
        print("You can now start the server: uvicorn main:app --host 0.0.0.0 --port 5001 --reload\n")

    finally:
        db.close()


if __name__ == "__main__":
    run()
