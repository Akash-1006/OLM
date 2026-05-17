# config.py
import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")         # From @BotFather
WEBHOOK_URL     = os.getenv("WEBHOOK_URL")            # Your public HTTPS URL
DATABASE_URL    = os.getenv("DATABASE_URL", "sqlite:///leads.db")
MINIAPP_BASE_URL = os.getenv("MINIAPP_BASE_URL", "").rstrip("/")

# Security
ADMIN_PASSWORD      = os.getenv("ADMIN_PASSWORD", "mcube@admin123")
MINIAPP_ACCESS_KEY  = os.getenv("MINIAPP_ACCESS_KEY", "")
MASTER_ADMIN_KEY    = os.getenv("MASTER_ADMIN_KEY", "")  # platform super-admin key

# Daily digest
DIGEST_OWNER_CHAT_ID = os.getenv("DIGEST_OWNER_CHAT_ID", "")
DIGEST_TIME_IST      = os.getenv("DIGEST_TIME_IST", "20:00")

# Quote template
QUOTE_TEMPLATE_DIR = os.getenv("QUOTE_TEMPLATE_DIR", "static")
