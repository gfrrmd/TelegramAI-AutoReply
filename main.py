import asyncio
import time
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters
from config import config
from database import Database
from ai_handler import AIHandler
from auth import (
    cmd_setup, cmd_cancel, setup_phone, setup_code, setup_password,
    PHONE_STEP, CODE_STEP, PASSWORD_STEP
)

WIB = timezone(timedelta(hours=7))

db = Database()
ai: AIHandler = None  # di-init setelah db.init() di main()

last_active: float = time.time()
pending: set = set()
user_client: TelegramClient = None
bot_instance: Bot = None


async def send_log_to_channel(sender_id: int, sender_name: str, incoming: str, reply: str):
    if not config.LOG_CHANNEL or not bot_instance:
        return
    try:
        now = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
        user_persona = await db.get_user_persona(sender_id)
        persona_label = "💚 Persona khusus" if user_persona else "🌏 Persona global"
        text = (
            f"🤖 **Auto-Reply Terkirim**\n"
            f"────────────────────\n"
            f"👤 **Dari:** {sender_name} (`{sender_id}`)\n"
            f"🕐 **Waktu:** {now}\n"
            f"{persona_label}\n"
            f"────────────────────\n"
            f"💬 **Pesan masuk:**\n{incoming}\n\n"
            f"🤖 **Balasan AI:**\n{reply}"
        )
        await bot_instance.send_message(
            chat_id=config.LOG_CHANNEL,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[Log Channel] Gagal kirim log: {e}")


async def start_user_client():
    global user_client
    session_str = await db.get_session()
    if not session_str:
        print("⚠️  Belum ada session. Kirim /setup ke bot untuk login.")
        return
    user_client = TelegramClient(StringSession(session_str), config.API_ID, config.API_HASH)
    await user_client.connect()
    if not await user_client.is_user_authorized():
        print("⚠️  Session tidak valid. Kirim /setup ulang ke bot.")
        user_client = None
        return
    me = await user_client.get_me()
    print(f"✅ User client aktif sebagai: {me.first_name} (@{me.username})")
    register_user_events()
    asyncio.ensure_future(user_client.run_until_disconnected())


def register_user_events():

    @user_client.on(events.NewMessage(outgoing=True))
    async def on_outgoing(event):
        global last_active
        last_active = time.time()

    @user_client.on(events.NewMessage(incoming=True))
    async def on_incoming(event):
        global last_active
        if not event.is_private:
            return
        sender = await event.get_sender()
        if not isinstance(sender, User):
            return
        if sender.bot:
            return

        sender_id = sender.id
        sender_name = sender.first_name or "Someone"

        if config.WHITELIST_ENABLED:
            if str(sender_id) not in config.WHITELIST_IDS:
                return
        if str(sender_id) in config.BLACKLIST_IDS:
            return

        is_active = await db.get_autoreply_status()
        if not is_active:
            return

        idle_seconds = time.time() - last_active
        if idle_seconds < config.IDLE_TIMEOUT:
            return

        if sender_id in pending:
            return
        pending.add(sender_id)

        try:
            await db.save_message(sender_id, "user", event.raw_text)
            history = await db.get_history(sender_id, limit=config.HISTORY_LIMIT)
            reply = await ai.generate_reply(
                sender_id=sender_id,
                sender_name=sender_name,
                history=history,
                new_message=event.raw_text
            )
            if reply:
                await asyncio.sleep(config.REPLY_DELAY)
                await event.reply(reply)
                await db.save_message(sender_id, "assistant", reply)
                await db.log_autoreply(sender_id, sender_name, event.raw_text, reply)
                await send_log_to_channel(sender_id, sender_name, event.raw_text, reply)
        finally:
            pending.discard(sender_id)

    @user_client.on(events.NewMessage(pattern=r"^/autoreply (on|off)$"))
    async def cmd_autoreply(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        status = event.pattern_match.group(1) == "on"
        await db.set_autoreply_status(status)
        await event.reply(f"✅ Auto-reply {'diaktifkan' if status else 'dinonaktifkan'}.")

    @user_client.on(events.NewMessage(pattern=r"^/status$"))
    async def cmd_status(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        is_active = await db.get_autoreply_status()
        idle = int(time.time() - last_active)
        log_ch = config.LOG_CHANNEL or "Tidak diaktifkan"
        await event.reply(
            f"📊 **Status Auto-Reply**\n"
            f"• Status: {'🟢 Aktif' if is_active else '🔴 Nonaktif'}\n"
            f"• Idle kamu: {idle} detik\n"
            f"• Timeout: {config.IDLE_TIMEOUT} detik\n"
            f"• Log channel: `{log_ch}`"
        )

    @user_client.on(events.NewMessage(pattern=r"^/setpersona (.+)$"))
    async def cmd_setpersona(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        persona = event.pattern_match.group(1)
        await db.set_persona(persona)
        await event.reply(f"✅ Persona global diubah:\n{persona}")

    @user_client.on(events.NewMessage(pattern=r"^/setuserpersona (\d+) (.+)$"))
    async def cmd_setuserpersona(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        sender_id = int(event.pattern_match.group(1))
        persona = event.pattern_match.group(2)
        try:
            target = await user_client.get_entity(sender_id)
            name = target.first_name or str(sender_id)
        except Exception:
            name = str(sender_id)
        await db.set_user_persona(sender_id, name, persona)
        await event.reply(
            f"💚 **Persona khusus disimpan untuk {name}** (`{sender_id}`):\n\n{persona}"
        )

    @user_client.on(events.NewMessage(pattern=r"^/deluserpersona (\d+)$"))
    async def cmd_deluserpersona(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        sender_id = int(event.pattern_match.group(1))
        deleted = await db.delete_user_persona(sender_id)
        if deleted:
            await event.reply(f"✅ Persona khusus untuk `{sender_id}` dihapus.")
        else:
            await event.reply(f"❌ Tidak ada persona khusus untuk `{sender_id}`.")

    @user_client.on(events.NewMessage(pattern=r"^/listpersona$"))
    async def cmd_listpersona(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        personas = await db.list_user_personas()
        if not personas:
            await event.reply("📭 Belum ada persona khusus.")
            return
        text = "💚 **Daftar Persona Khusus:**\n\n"
        for p in personas:
            text += f"👤 **{p['sender_name']}** (`{p['sender_id']}`)\n"
            text += f"📝 {p['persona'][:100]}{'...' if len(p['persona']) > 100 else ''}\n\n"
        await event.reply(text)

    @user_client.on(events.NewMessage(pattern=r"^/clearhistory (\d+)$"))
    async def cmd_clear(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        user_id = int(event.pattern_match.group(1))
        await db.clear_history(user_id)
        await event.reply(f"🗑️ Riwayat percakapan dengan `{user_id}` dihapus.")

    @user_client.on(events.NewMessage(pattern=r"^/logs$"))
    async def cmd_logs(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        logs = await db.get_logs(limit=10)
        if not logs:
            await event.reply("📭 Belum ada log auto-reply.")
            return
        text = "📋 **10 Log Terakhir:**\n\n"
        for log in logs:
            text += f"👤 **{log['sender_name']}** (`{log['sender_id']}`)\n"
            text += f"💬 {log['incoming'][:80]}\n"
            text += f"🤖 {log['reply'][:80]}\n"
            text += f"🕐 {log['created_at']}\n\n"
        await event.reply(text)

    @user_client.on(events.NewMessage(pattern=r"^/help$"))
    async def cmd_help(event):
        if event.chat_id != (await user_client.get_me()).id:
            return
        await event.reply(
            "🤖 **TelegramAI AutoReply — Commands**\n\n"
            "🔧 **Auto-Reply**\n"
            "`/autoreply on` — Aktifkan\n"
            "`/autoreply off` — Nonaktifkan\n"
            "`/status` — Cek status, idle time & log channel\n\n"
            "🧠 **Persona Global**\n"
            "`/setpersona <teks>` — Ubah persona default AI\n\n"
            "💚 **Persona Khusus per Orang**\n"
            "`/setuserpersona <user_id> <prompt>` — Set prompt khusus\n"
            "`/deluserpersona <user_id>` — Hapus prompt khusus\n"
            "`/listpersona` — Lihat semua prompt khusus\n\n"
            "🗄️ **Riwayat & Log**\n"
            "`/clearhistory <user_id>` — Hapus riwayat chat\n"
            "`/logs` — Lihat 10 log terakhir\n\n"
            "💡 Kirim command ini ke **Saved Messages** kamu."
        )


async def main():
    global bot_instance, ai

    await db.init()
    print("✅ Database siap.")

    # ── Init AIHandler setelah db.init() agar pool sudah tersedia
    ai = AIHandler(db)
    print("✅ AI Handler siap.")

    # ── Build PTB app
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    bot_instance = app.bot

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", cmd_setup)],
        states={
            PHONE_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_phone)],
            CODE_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_code)],
            PASSWORD_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_password)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )
    app.add_handler(conv_handler)

    # ── Jalankan PTB secara manual (non-blocking) agar tidak konflik event loop dengan Telethon
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("🤖 Bot PTB berjalan. Kirim /setup ke bot untuk login.")

    # ── Jalankan Telethon user client di event loop yang sama
    await start_user_client()

    # ── Jaga program tetap berjalan
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
