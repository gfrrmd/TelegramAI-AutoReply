# auth.py tidak lagi digunakan.
# Semua logic /setup sudah dipindah ke main.py (register_bot_events)
# File ini dipertahankan agar tidak breaking import yang mungkin tersisa.

PHONE_STEP = 1
CODE_STEP = 2
PASSWORD_STEP = 3

_db = None

def set_db(db_instance):
    global _db
    _db = db_instance
