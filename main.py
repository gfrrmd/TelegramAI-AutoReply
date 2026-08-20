import asyncio
import time
from telethon import TelegramClient, events
from telethon.tl.types import User
from config import config
from database import Database
from ai_handler import AIHandler

db = Database()
ai = AIHandler()

client = TelegramClient(
    "session/account",
    config.API_ID,
    config.API_HASH
)

# Track waktu terakhir user aktif (kirim pesan)
last_active: float = time.time()

# Track percakapan yang sedang diproses agar tidak double-reply
pending: set = set()


@client.on(events.NewMessage(outgoing=True))
async def on_outgoing(event):
    """Update last_active setiap kali user kirim pesan sendiri."""
    global last_active
    last_active = time.time()


@client.on(events.NewMessage(incoming=True))
async def on_incoming(event):
    """Handle pesan masuk."""
    global last_active

    # Abaikan pesan dari grup/channel kalau tidak diaktifkan
    if not event.is_private:
        return

    sender = await event.get_sender()
    if not isinstance(sender, User):
        return

    sender_id = sender.id
    sender_name = sender.first_name or "Someone"

    # Cek apakah sender di-whitelist (kalau whitelist aktif)
    if config.WHITELIST_ENABLED:
        if str(sender_id) not in config.WHITELIST_IDS:
            return

    # Cek apakah sender di-blacklist
    if str(sender_id) in config.BLACKLIST_IDS:
        return

    # Cek apakah auto-reply aktif di database
    is_active = await db.get_autoreply_status()
    if not is_active:
        return

    # Cek apakah user sedang aktif (tidak idle)
    idle_seconds = time.time() - last_active
    if idle_seconds < config.IDLE_TIMEOUT:
        return

    # Hindari double reply untuk sender yang sama
    if sender_id in pending:
        return
    pending.add(sender_id)

    try:
        # Simpan pesan masuk ke database
        await db.save_message(sender_id, "user", event.raw_text)

        # Ambil riwayat percakapan
        history = await db.get_history(sender_id, limit=config.HISTORY_LIMIT)

        # Generate balasan dari Gemini
        reply = await ai.generate_reply(
            sender_name=sender_name,
            history=history,
            new_message=event.raw_text
        )

        if reply:
            await asyncio.sleep(config.REPLY_DELAY)
            await event.reply(reply)
            await db.save_message(sender_id, "assistant", reply)
            await db.log_autoreply(sender_id, sender_name, event.raw_text, reply)
    finally:
        pending.discard(sender_id)


@client.on(events.NewMessage(outgoing=False, pattern=r"^/autoreply (on|off)$"))
async def cmd_autoreply(event):
    """Command: /autoreply on|off — hanya bisa dipakai dari akun sendiri via Saved Messages."""
    if event.chat_id != (await client.get_me()).id:
        return
    status = event.pattern_match.group(1) == "on"
    await db.set_autoreply_status(status)
    await event.reply(f"✅ Auto-reply {'diaktifkan' if status else 'dinonaktifkan'}.")


@client.on(events.NewMessage(outgoing=False, pattern=r"^/status$"))
async def cmd_status(event):
    """Command: /status — cek status auto-reply."""
    if event.chat_id != (await client.get_me()).id:
        return
    is_active = await db.get_autoreply_status()
    idle = int(time.time() - last_active)
    await event.reply(
        f"📊 **Status Auto-Reply**\n"
        f"• Status: {'🟢 Aktif' if is_active else '🔴 Nonaktif'}\n"
        f"• Idle kamu: {idle} detik\n"
        f"• Timeout: {config.IDLE_TIMEOUT} detik"
    )


@client.on(events.NewMessage(outgoing=False, pattern=r"^/clearhistory (\d+)$"))
async def cmd_clear(event):
    """Command: /clearhistory <user_id> — hapus riwayat percakapan."""
    if event.chat_id != (await client.get_me()).id:
        return
    user_id = int(event.pattern_match.group(1))
    await db.clear_history(user_id)
    await event.reply(f"🗑️ Riwayat percakapan dengan {user_id} dihapus.")


@client.on(events.NewMessage(outgoing=False, pattern=r"^/logs$"))
async def cmd_logs(event):
    """Command: /logs — lihat 10 log auto-reply terakhir."""
    if event.chat_id != (await client.get_me()).id:
        return
    logs = await db.get_logs(limit=10)
    if not logs:
        await event.reply("📭 Belum ada log auto-reply.")
        return
    text = "📋 **10 Log Terakhir:**\n\n"
    for log in logs:
        text += f"👤 **{log['sender_name']}** ({log['sender_id']})\n"
        text += f"💬 Pesan: {log['incoming'][:80]}\n"
        text += f"🤖 Balas: {log['reply'][:80]}\n"
        text += f"🕐 {log['created_at']}\n\n"
    await event.reply(text)


@client.on(events.NewMessage(outgoing=False, pattern=r"^/setpersona (.+)$"))
async def cmd_persona(event):
    """Command: /setpersona <teks> — ubah persona/system prompt AI."""
    if event.chat_id != (await client.get_me()).id:
        return
    persona = event.pattern_match.group(1)
    await db.set_persona(persona)
    await event.reply(f"✏️ Persona AI diubah:\n{persona}")


@client.on(events.NewMessage(outgoing=False, pattern=r"^/help$"))
async def cmd_help(event):
    """Command: /help — tampilkan daftar command."""
    if event.chat_id != (await client.get_me()).id:
        return
    await event.reply(
        "🤖 **TelegramAI AutoReply — Commands**\n\n"
        "`/autoreply on` — Aktifkan auto-reply\n"
        "`/autoreply off` — Nonaktifkan auto-reply\n"
        "`/status` — Cek status & idle time\n"
        "`/setpersona <teks>` — Ubah persona AI\n"
        "`/clearhistory <user_id>` — Hapus riwayat chat\n"
        "`/logs` — Lihat 10 log auto-reply terakhir\n"
        "`/help` — Tampilkan pesan ini\n\n"
        "💡 Kirim command ini ke **Saved Messages** kamu."
    )


async def main():
    await db.init()
    print("✅ Database siap.")
    await client.start(phone=config.PHONE_NUMBER)
    me = await client.get_me()
    print(f"✅ Login sebagai: {me.first_name} (@{me.username})")
    print("🤖 TelegramAI AutoReply berjalan...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
