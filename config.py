import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо указать TELEGRAM_TOKEN в .env файле")

MIN_BET = int(os.getenv("MIN_BET", 1))
MAX_BET = int(os.getenv("MAX_BET", 100000))
MIN_WITHDRAWAL = int(os.getenv("MIN_WITHDRAWAL", 500))