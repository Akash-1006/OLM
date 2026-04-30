# config.py
import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # From @BotFather
WEBHOOK_URL    = os.getenv('WEBHOOK_URL')     # Your public HTTPS URL
DATABASE_URL   = os.getenv('DATABASE_URL', 'sqlite:///leads.db')