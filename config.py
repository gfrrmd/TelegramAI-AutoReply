import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    PHONE_NUMBER: str = os.getenv("PHONE_NUMBER", "")

    # Google Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Database (Railway PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Auto-reply settings
    IDLE_TIMEOUT: int = int(os.getenv("IDLE_TIMEOUT", "300"))  # detik (default 5 menit)
    REPLY_DELAY: int = int(os.getenv("REPLY_DELAY", "3"))       # detik sebelum balas (biar natural)
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10")) # jumlah pesan riwayat

    # Whitelist/Blacklist (pisahkan dengan koma, contoh: "123456,789012")
    WHITELIST_ENABLED: bool = os.getenv("WHITELIST_ENABLED", "false").lower() == "true"
    WHITELIST_IDS: list = os.getenv("WHITELIST_IDS", "").split(",") if os.getenv("WHITELIST_IDS") else []
    BLACKLIST_IDS: list = os.getenv("BLACKLIST_IDS", "").split(",") if os.getenv("BLACKLIST_IDS") else []


config = Config()
