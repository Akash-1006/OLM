# OLM SaaS

**On-site Lead Management** — multi-tenant SaaS for concrete/construction sales teams.

## Stack

- **Backend:** FastAPI + Python-telegram-bot v21 + APScheduler
- **Database:** SQLite (dev) / PostgreSQL (prod) via SQLAlchemy
- **Frontend:** Telegram Mini App (HTML/JS) + Admin Dashboard + Master Admin Panel

---

## Quick Start (Development)

```bash
# 1. Clone and create virtualenv
git clone https://github.com/Akash-1006/OLM
cd OLM
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and fill env vars
cp .env.example .env
# Edit .env with your TELEGRAM_TOKEN, WEBHOOK_URL, etc.

# 4. Run DB migration (first time, or after pulling this branch)
python -m migrations.add_tenant_id

# 5. Start server
uvicorn main:app --host 0.0.0.0 --port 5001 --reload
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | ✅ | Bot token from @BotFather |
| `WEBHOOK_URL` | ✅ | Public HTTPS URL of this server |
| `DATABASE_URL` | ✅ prod | `sqlite:///leads.db` (dev) or `postgresql://...` (prod) |
| `MASTER_ADMIN_KEY` | ✅ | Password for `/master/*` API endpoints |
| `ADMIN_PASSWORD` | ✅ | Default tenant admin password (fallback) |
| `MINIAPP_ACCESS_KEY` | | Default tenant mini-app access key |
| `DIGEST_OWNER_CHAT_ID` | | Telegram chat_id for daily digest |
| `DEFAULT_TENANT_SLUG` | | Slug for backward-compat single-tenant mode (default: `default`) |
| `DIGEST_TIME_IST` | | Daily digest time e.g. `20:00` (default: 8 PM IST) |

---

## SaaS Architecture

```
┌──────────────────────────────────────────────────┐
│ Master Admin Panel /master-admin/       │
│  └─ Manage Tenants, Plans, Defaults      │
├──────────────────────────────────────────────────┤
│ Tenant A              Tenant B           │
│  ├─ Admin Dashboard     ├─ Admin Dashboard │
│  └─ Telegram Mini App  └─ Telegram Mini App│
├──────────────────────────────────────────────────┤
│ FastAPI (main.py)                        │
│  ├─ /webhook       Telegram updates      │
│  ├─ /miniapp/      Mini app routes        │
│  ├─ /admin/        Tenant admin API       │
│  └─ /master/       Platform master API    │
└──────────────────────────────────────────────────┘
```

---

## Creating Your First Tenant (after migration)

```bash
curl -X POST https://your-server.com/master/tenants \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'admin:YOUR_MASTER_KEY' | base64)" \
  -d '{
    "name": "Titans Concrete",
    "slug": "titans",
    "plan": "pro",
    "telegram_token": "123456:ABC...",
    "webhook_url": "https://your-server.com",
    "admin_password": "titans-admin-pass",
    "digest_owner_chat_id": "123456789"
  }'
```

Or use the **Master Admin Panel** at `https://your-server.com/master-admin/`.

---

## Key URLs

| URL | Purpose |
|---|---|
| `/health` | Health check |
| `/webhook` | Telegram webhook endpoint |
| `/miniapp/` | Mini app HTML |
| `/admin/` | Admin dashboard HTML |
| `/master-admin/` | Master admin panel HTML |
| `/master/tenants` | Tenant CRUD API |
| `/master/stats` | Platform stats |
| `/docs` | Auto-generated FastAPI docs |

---

## Running DB Migration on Existing Data

If you have an existing SQLite database with leads, run the migration once to add `tenant_id` columns and create a default tenant:

```bash
export DEFAULT_TENANT_NAME="Your Company"
export DEFAULT_TENANT_SLUG="default"
export ADMIN_PASSWORD="your-admin-pass"
export MINIAPP_ACCESS_KEY="your-miniapp-key"
export MINIAPP_BASE_URL="https://your-server.com"
export BRAND_NAME="YourBrand"

python -m migrations.add_tenant_id
```

All existing leads will be assigned to this default tenant automatically.

---

## Deployment (Render / Railway / VPS)

### Render
```bash
# Uses render.yaml automatically
git push origin saas-multitenancy
# Connect repo in Render dashboard, it picks up render.yaml
```

### VPS / Docker
```bash
uvicorn main:app --host 0.0.0.0 --port 5001 --workers 1
# Note: use workers=1 with APScheduler to avoid duplicate jobs
```
