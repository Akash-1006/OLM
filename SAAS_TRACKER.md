# OLM SaaS Migration Tracker

> **Branch:** `saas-multitenancy`
> **Goal:** Convert the hardcoded single-tenant OLM app into a fully configurable multi-tenant SaaS.
> **Last updated:** 2026-05-17

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Committed to `saas-multitenancy` |
| 🔄 | In Progress |
| ⏳ | Queued / Not Started |

---

## Phase 1 — Foundations (Framework + Scaffold)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1.1 | Replace Flask with FastAPI; add uvicorn | `requirements.txt` | ✅ |
| 1.2 | Add `dependencies.py` — `get_db`, `get_current_tenant`, `require_tenant_admin`, `require_app_auth`, `require_master_admin` | `dependencies.py` | ✅ |
| 1.3 | Add `main.py` — FastAPI app with lifespan (replaces `app.py`) | `main.py` | ✅ |
| 1.4 | Add `routers/webhook.py` — Telegram webhook | `routers/webhook.py` | ✅ |
| 1.5 | Add `routers/miniapp.py` — all mini app routes, tenant-aware | `routers/miniapp.py` | ✅ |

---

## Phase 2 — Data Model (Multi-tenancy)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 2.1 | Add `models/tenant.py` — Tenant table | `models/tenant.py` | ✅ |
| 2.2 | Add `models/tenant_config.py` — KV config store per tenant | `models/tenant_config.py` | ✅ |
| 2.3 | Add `models/platform_admin.py` — master admin accounts | `models/platform_admin.py` | ✅ |
| 2.4 | Update `models/__init__.py` to include all models | `models/__init__.py` | ✅ |
| 2.5 | Update `models/exec_target.py` — add `tenant_id` FK | `models/exec_target.py` | ✅ |
| 2.6 | Add `migrations/add_tenant_id.py` — one-time DB migration | `migrations/add_tenant_id.py` | ✅ |
| 2.7 | Add `tenant_id` to `models/lead.py` | `models/lead.py` | ⏳ |
| 2.8 | Add `tenant_id` to `models/lead_update.py` | `models/lead_update.py` | ⏳ |

---

## Phase 3 — Admin APIs

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 3.1 | Add `routers/admin.py` — tenant admin API (leads, stats, export, config, targets) | `routers/admin.py` | ✅ |
| 3.2 | Add `routers/master_admin.py` — master admin API (tenants, config defaults, stats) | `routers/master_admin.py` | ✅ |
| 3.3 | Add `GET /api/tenant-config` endpoint in miniapp router (serves dropdown data) | `routers/miniapp.py` | ✅ |

---

## Phase 4 — Frontend Wiring (Mini App + Admin Dashboard)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 4.1 | Mini app JS: replace hardcoded dropdown arrays with `fetch("/api/tenant-config")` | `miniapp/index.html` | ⏳ |
| 4.2 | Mini app JS: remove hardcoded `MINIAPP_BASE_URL` constant; derive from served URL | `miniapp/index.html` | ⏳ |
| 4.3 | Admin dashboard: replace hardcoded API base with tenant-resolved URL | `admin_dashboard/` | ⏳ |
| 4.4 | Admin dashboard: add tenant config editor UI (stages, materials, statuses, brand) | `admin_dashboard/` | ⏳ |
| 4.5 | Admin dashboard: add per-exec target editor UI | `admin_dashboard/` | ⏳ |
| 4.6 | Mini app JS: display tenant `brand_name` and `brand_color` from config | `miniapp/index.html` | ⏳ |

---

## Phase 5 — Master Admin Panel (UI)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 5.1 | Build master admin HTML panel | `master_admin/index.html` | ⏳ |
| 5.2 | Tenant list + status badges + lead counts | `master_admin/index.html` | ⏳ |
| 5.3 | Create Tenant form (name, slug, plan, bot token, admin password) | `master_admin/index.html` | ⏳ |
| 5.4 | Edit Tenant modal (status, plan, branding, keys) | `master_admin/index.html` | ⏳ |
| 5.5 | Suspend / Activate tenant buttons | `master_admin/index.html` | ⏳ |
| 5.6 | Rotate miniapp key button + copy-to-clipboard | `master_admin/index.html` | ⏳ |
| 5.7 | Platform stats dashboard (total tenants, total leads, per-tenant) | `master_admin/index.html` | ⏳ |
| 5.8 | Platform defaults editor (stages, materials, statuses, targets) | `master_admin/index.html` | ⏳ |

---

## Phase 6 — Env, Config, Deployment

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 6.1 | Add `.env.example` with all SaaS variables documented | `.env.example` | ✅ |
| 6.2 | Update `config.py` to read `DATABASE_URL` and `MASTER_ADMIN_PASSWORD` | `config.py` | ⏳ |
| 6.3 | Update `db.py` to use `DATABASE_URL` env var (SQLite dev, Postgres prod) | `db.py` | ⏳ |
| 6.4 | Add `Procfile` / `render.yaml` or `docker-compose.yml` for deployment | deployment files | ⏳ |
| 6.5 | Update `README.md` with SaaS setup instructions (migration, env vars, first tenant) | `README.md` | ⏳ |

---

## Phase 7 — Testing & Hardening

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 7.1 | Test: create tenant via master admin API | `tests/` | ⏳ |
| 7.2 | Test: submit lead through tenant miniapp | `tests/` | ⏳ |
| 7.3 | Test: tenant isolation (exec from tenant A cannot see tenant B data) | `tests/` | ⏳ |
| 7.4 | Test: config changes in master admin reflect in miniapp dropdown | `tests/` | ⏳ |
| 7.5 | Test: suspended tenant returns 404 on all API calls | `tests/` | ⏳ |
| 7.6 | Add rate limiting (slowapi or Cloudflare) | `main.py` | ⏳ |
| 7.7 | Add audit log table (`AuditLog`) for admin actions | `models/audit_log.py` | ⏳ |

---

## How to Run the Migration on Existing Data

```bash
# 1. Activate your virtualenv
source venv/bin/activate

# 2. Set env vars (or ensure .env is loaded)
export DEFAULT_TENANT_NAME="YourCompany"
export DEFAULT_TENANT_SLUG="yourcompany"
export ADMIN_PASSWORD="your-admin-password"
export MINIAPP_ACCESS_KEY="your-miniapp-key"
export MINIAPP_BASE_URL="https://your-domain.com"
export BRAND_NAME="YourBrand"

# 3. Run migration
python -m migrations.add_tenant_id

# 4. Start the new FastAPI server
uvicorn main:app --host 0.0.0.0 --port 5001
```

---

## Key Env Vars for SaaS

| Variable | Purpose |
|----------|---------|
| `MASTER_ADMIN_PASSWORD` | Protects all `/master/...` endpoints |
| `DATABASE_URL` | SQLite (dev) or Postgres (prod) |
| `TELEGRAM_TOKEN` | Platform-level bot token |
| `WEBHOOK_URL` | Public URL of this server |
| `DEFAULT_TENANT_SLUG` | Slug for backward-compat single-tenant mode |
| `ADMIN_PASSWORD` | Default tenant admin password (fallback) |
| `MINIAPP_ACCESS_KEY` | Default tenant miniapp key (fallback) |

---

## Next Steps

1. Run `python -m migrations.add_tenant_id` on your existing DB.
2. Start the server with `uvicorn main:app`.
3. Use the master admin API at `/master/` to create new tenants.
4. Wire miniapp JS to fetch config from `/api/tenant-config` (Phase 4).
5. Build the master admin HTML panel (Phase 5).
