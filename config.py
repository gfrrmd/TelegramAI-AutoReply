import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram API (dari my.telegram.org)
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")

    # Bot Token (dari @BotFather)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Owner ID (Telegram user ID kamu)
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))

    # Log Channel (channel ID atau username, contoh: -1001234567890 atau @namalog)
    # Kosongkan jika tidak ingin log ke channel
    LOG_CHANNEL: str = os.getenv("LOG_CHANNEL", "")

    # Google Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Database (Railway PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Auto-reply settings
    IDLE_TIMEOUT: int = int(os.getenv("IDLE_TIMEOUT", "300"))
    REPLY_DELAY: int = int(os.getenv("REPLY_DELAY", "3"))
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10"))

    # Whitelist/Blacklist
    WHITELIST_ENABLED: bool = os.getenv("WHITELIST_ENABLED", "false").lower() == "true"
    WHITELIST_IDS: list = os.getenv("WHITELIST_IDS", "").split(",") if os.getenv("WHITELIST_IDS") else []
    BLACKLIST_IDS: list = os.getenv("BLACKLIST_IDS", "").split(",") if os.getenv("BLACKLIST_IDS") else []


config = Config()
