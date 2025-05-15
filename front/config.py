import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(admin_id.strip()) for admin_id in os.getenv("ADMINS", "").split(",")] if os.getenv("ADMINS") else []
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения.")
