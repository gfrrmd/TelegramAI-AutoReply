import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError
from config import config

PHONE_STEP = 1
CODE_STEP = 2
PASSWORD_STEP = 3

# db di-inject dari main.py setelah db.init() selesai
_db = None


def set_db(db_instance):
    """Inject db instance dari main.py agar pakai pool yang sudah di-init."""
    global _db
    _db = db_instance


# Temporary store selama proses login
temp_store: dict = {}


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != str(config.OWNER_ID):
        await update.message.reply_text("❌ Kamu tidak punya akses untuk command ini.")
        return ConversationHandler.END

    temp_store.pop(uid, None)
    await update.message.reply_text(
        "🤖 *Setup TelegramAI AutoReply*\n\n"
        "Proses ini menghubungkan akun Telegram kamu ke bot.\n\n"
        "*Langkah 1/3 — Nomor HP 📲*\n\n"
        "Masukkan nomor HP Telegram kamu.\n"
        "Contoh: `+6281234567890`\n\n"
        "Kirim nomor HP kamu, atau /cancel untuk batal:",
        parse_mode="Markdown"
    )
    return PHONE_STEP


async def setup_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    phone = update.message.text.strip()

    client = TelegramClient(StringSession(), config.API_ID, config.API_HASH)
    try:
        await client.connect()
        result = await client.send_code_request(phone)
        temp_store[uid] = {
            "phone": phone,
            "phone_hash": result.phone_code_hash,
            "client": client
        }
        await update.message.reply_text(
            "📨 Kode OTP dikirim ke Telegram kamu!\n\n"
            "*Langkah 2/3 — Kode OTP 🔢*\n\n"
            "Ketik kode dengan spasi di antara tiap angka.\n"
            "✅ Contoh: `1 2 3 4 5`\n\n"
            "Kirim kode OTP kamu, atau /cancel untuk batal:",
            parse_mode="Markdown"
        )
        return CODE_STEP
    except Exception as e:
        await client.disconnect()
        temp_store.pop(uid, None)
        await update.message.reply_text(f"❌ Gagal kirim OTP: {e}\n\nCoba /setup ulang.")
        return ConversationHandler.END


async def setup_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = update.message.text.strip().replace(" ", "")
    data = temp_store.get(uid, {})
    client = data.get("client")

    try:
        await client.sign_in(data["phone"], code, phone_code_hash=data["phone_hash"])
    except SessionPasswordNeededError:
        await update.message.reply_text(
            "🔐 Akun kamu mengaktifkan 2FA.\n\n"
            "*Langkah 3/3 — Password 2FA*\n\n"
            "Masukkan password 2FA Telegram kamu, atau /cancel untuk batal:",
            parse_mode="Markdown"
        )
        return PASSWORD_STEP
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        await client.disconnect()
        temp_store.pop(uid, None)
        await update.message.reply_text("❌ Kode OTP salah/kadaluarsa. Coba /setup ulang.")
        return ConversationHandler.END
    except Exception as e:
        await client.disconnect()
        temp_store.pop(uid, None)
        await update.message.reply_text(f"❌ Error: {e}\n\nCoba /setup ulang.")
        return ConversationHandler.END

    return await _finish_setup(update, uid, client)


async def setup_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = temp_store.get(uid, {})
    client = data.get("client")

    try:
        await client.sign_in(password=update.message.text.strip())
    except Exception as e:
        await client.disconnect()
        temp_store.pop(uid, None)
        await update.message.reply_text(f"❌ Password 2FA salah: {e}\n\nCoba /setup ulang.")
        return ConversationHandler.END

    return await _finish_setup(update, uid, client)


async def _finish_setup(update: Update, uid: int, client: TelegramClient):
    from main import start_user_client

    string_session = client.session.save()

    # Simpan session pakai _db yang sudah di-init dari main.py
    await _db.save_session(string_session)
    await client.disconnect()
    temp_store.pop(uid, None)

    await update.message.reply_text(
        "✅ *Setup berhasil! Akun kamu sudah terhubung.*\n\n"
        "⚠️ *PENTING:* Jangan logout dari sesi Telegram ini.\n\n"
        "🤖 Auto-reply AI sudah aktif. Gunakan command berikut via *Saved Messages*:\n"
        "`/autoreply on|off` — aktifkan/nonaktifkan\n"
        "`/status` — cek status\n"
        "`/setpersona <teks>` — ubah persona AI\n"
        "`/logs` — lihat log balasan\n"
        "`/help` — semua command",
        parse_mode="Markdown"
    )

    # Restart user client dengan session baru
    await start_user_client()
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = temp_store.pop(uid, {})
    client = data.get("client")
    if client:
        await client.disconnect()
    await update.message.reply_text("❌ Setup dibatalkan.")
    return ConversationHandler.END
