import asyncio
import time
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from config import config
from database import Database
from ai_handler import AIHandler

WIB = timezone(timedelta(hours=7))

db = Database()
ai: AIHandler = None

last_active: float = time.time()
pending: set = set()
user_client: TelegramClient = None   # akun user (userbot)
bot_client: TelegramClient = None    # bot token (untuk /setup)
my_id: int = None


async def send_log_to_channel(sender_id: int, sender_name: str, incoming: str, reply: str):
    if not config.LOG_CHANNEL:
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
        await bot_client.send_message(int(config.LOG_CHANNEL), text)
    except Exception as e:
        print(f"[Log] Gagal kirim log: {e}")


async def start_user_client():
    global user_client, my_id
    session_str = await db.get_session()
    if not session_str:
        print("⚠️ Belum ada session. Kirim /setup ke bot untuk login.")
        return
    if user_client and user_client.is_connected():
        await user_client.disconnect()
    user_client = TelegramClient(StringSession(session_str), config.API_ID, config.API_HASH)
    await user_client.connect()
    if not await user_client.is_user_authorized():
        print("⚠️ Session tidak valid. Kirim /setup ulang ke bot.")
        user_client = None
        return
    me = await user_client.get_me()
    my_id = me.id
    print(f"✅ User client: {me.first_name} (@{me.username}) | ID: {my_id}")
    register_userbot_events()
    asyncio.ensure_future(user_client.run_until_disconnected())


def register_userbot_events():

    @user_client.on(events.NewMessage(outgoing=True))
    async def on_outgoing(event):
        global last_active
        last_active = time.time()

    @user_client.on(events.NewMessage(incoming=True))
    async def on_incoming(event):
        if not event.is_private:
            return
        sender = await event.get_sender()
        if not isinstance(sender, User) or sender.bot:
            return

        sender_id = sender.id
        sender_name = sender.first_name or "Someone"

        if config.WHITELIST_ENABLED and str(sender_id) not in config.WHITELIST_IDS:
            return
        if str(sender_id) in config.BLACKLIST_IDS:
            return

        is_active = await db.get_autoreply_status()
        if not is_active:
            return

        if (time.time() - last_active) < config.IDLE_TIMEOUT:
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

    # ── Commands via Saved Messages ───────────────────────────

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/autoreply (on|off)$"))
    async def cmd_autoreply(event):
        if event.chat_id != my_id:
            return
        status = event.pattern_match.group(1) == "on"
        await db.set_autoreply_status(status)
        await event.reply(f"✅ Auto-reply {'diaktifkan' if status else 'dinonaktifkan'}.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/status$"))
    async def cmd_status(event):
        if event.chat_id != my_id:
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

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/setpersona (.+)$"))
    async def cmd_setpersona(event):
        if event.chat_id != my_id:
            return
        persona = event.pattern_match.group(1)
        await db.set_persona(persona)
        await event.reply(f"✅ Persona global diubah:\n{persona}")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/setuserpersona (\d+) (.+)$"))
    async def cmd_setuserpersona(event):
        if event.chat_id != my_id:
            return
        sender_id = int(event.pattern_match.group(1))
        persona = event.pattern_match.group(2)
        try:
            target = await user_client.get_entity(sender_id)
            name = target.first_name or str(sender_id)
        except Exception:
            name = str(sender_id)
        await db.set_user_persona(sender_id, name, persona)
        await event.reply(f"💚 Persona khusus disimpan untuk **{name}** (`{sender_id}`):\n\n{persona}")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/deluserpersona (\d+)$"))
    async def cmd_deluserpersona(event):
        if event.chat_id != my_id:
            return
        sender_id = int(event.pattern_match.group(1))
        deleted = await db.delete_user_persona(sender_id)
        await event.reply(
            f"✅ Persona khusus untuk `{sender_id}` dihapus." if deleted
            else f"❌ Tidak ada persona khusus untuk `{sender_id}`."
        )

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/listpersona$"))
    async def cmd_listpersona(event):
        if event.chat_id != my_id:
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

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/clearhistory (\d+)$"))
    async def cmd_clear(event):
        if event.chat_id != my_id:
            return
        user_id = int(event.pattern_match.group(1))
        await db.clear_history(user_id)
        await event.reply(f"🗑️ Riwayat chat dengan `{user_id}` dihapus.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/logs$"))
    async def cmd_logs(event):
        if event.chat_id != my_id:
            return
        logs = await db.get_logs(limit=10)
        if not logs:
            await event.reply("📭 Belum ada log.")
            return
        text = "📋 **10 Log Terakhir:**\n\n"
        for log in logs:
            text += f"👤 **{log['sender_name']}** (`{log['sender_id']}`)\n"
            text += f"💬 {log['incoming'][:80]}\n🤖 {log['reply'][:80]}\n🕐 {log['created_at']}\n\n"
        await event.reply(text)

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/help$"))
    async def cmd_help(event):
        if event.chat_id != my_id:
            return
        await event.reply(
            "🤖 **TelegramAI AutoReply — Commands**\n\n"
            "🔧 `/autoreply on/off` — Aktifkan/nonaktifkan\n"
            "📊 `/status` — Cek status\n"
            "🧠 `/setpersona <teks>` — Ubah persona global\n"
            "💚 `/setuserpersona <id> <prompt>` — Persona khusus\n"
            "📋 `/listpersona` — Daftar persona khusus\n"
            "❌ `/deluserpersona <id>` — Hapus persona khusus\n"
            "🗑️ `/clearhistory <id>` — Hapus riwayat chat\n"
            "📜 `/logs` — 10 log terakhir\n\n"
            "💡 Kirim di **Saved Messages** kamu."
        )


def register_bot_events():
    """Handler /setup via bot client (Telethon bot)."""
    # State per user
    setup_state: dict = {}

    @bot_client.on(events.NewMessage(pattern=r"^/start$"))
    async def cmd_start(event):
        if event.sender_id != config.OWNER_ID:
            return
        await event.reply(
            "🤖 **TelegramAI AutoReply**\n\n"
            "Kirim /setup untuk menghubungkan akun Telegram kamu."
        )

    @bot_client.on(events.NewMessage(pattern=r"^/setup$"))
    async def cmd_setup(event):
        if event.sender_id != config.OWNER_ID:
            await event.reply("❌ Kamu tidak punya akses.")
            return
        setup_state[event.sender_id] = {"step": "phone"}
        await event.reply(
            "🤖 *Setup TelegramAI AutoReply*\n\n"
            "*Langkah 1/3 — Nomor HP 📲*\n"
            "Masukkan nomor HP Telegram kamu.\n"
            "Contoh: `+6281234567890`\n\n"
            "Atau /cancel untuk batal.",
            parse_mode="md"
        )

    @bot_client.on(events.NewMessage(pattern=r"^/cancel$"))
    async def cmd_cancel(event):
        if event.sender_id != config.OWNER_ID:
            return
        data = setup_state.pop(event.sender_id, {})
        client = data.get("client")
        if client:
            await client.disconnect()
        await event.reply("❌ Setup dibatalkan.")

    @bot_client.on(events.NewMessage)
    async def handle_text(event):
        if event.sender_id != config.OWNER_ID:
            return
        if event.text and event.text.startswith("/"):
            return

        uid = event.sender_id
        state = setup_state.get(uid)
        if not state:
            return

        step = state.get("step")

        if step == "phone":
            from telethon import TelegramClient as TC
            from telethon.sessions import StringSession as SS
            phone = event.text.strip()
            client = TC(SS(), config.API_ID, config.API_HASH)
            await client.connect()
            try:
                result = await client.send_code_request(phone)
                state.update({"step": "code", "phone": phone,
                              "hash": result.phone_code_hash, "client": client})
                await event.reply(
                    "📨 Kode OTP dikirim!\n\n"
                    "*Langkah 2/3 — Kode OTP 🔢*\n"
                    "Ketik kode dengan spasi: `1 2 3 4 5`\n\n"
                    "Atau /cancel untuk batal.",
                    parse_mode="md"
                )
            except Exception as e:
                await client.disconnect()
                setup_state.pop(uid, None)
                await event.reply(f"❌ Gagal kirim OTP: {e}\n\nCoba /setup ulang.")

        elif step == "code":
            from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
            code = event.text.strip().replace(" ", "")
            client = state["client"]
            try:
                await client.sign_in(state["phone"], code, phone_code_hash=state["hash"])
                await _finish_setup(event, uid, client)
            except SessionPasswordNeededError:
                state["step"] = "password"
                await event.reply(
                    "🔐 Akun kamu aktifkan 2FA.\n\n"
                    "*Langkah 3/3 — Password 2FA*\n"
                    "Masukkan password 2FA kamu.\n\n"
                    "Atau /cancel untuk batal.",
                    parse_mode="md"
                )
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                await client.disconnect()
                setup_state.pop(uid, None)
                await event.reply("❌ Kode OTP salah/kadaluarsa. Coba /setup ulang.")
            except Exception as e:
                await client.disconnect()
                setup_state.pop(uid, None)
                await event.reply(f"❌ Error: {e}\n\nCoba /setup ulang.")

        elif step == "password":
            client = state["client"]
            try:
                await client.sign_in(password=event.text.strip())
                await _finish_setup(event, uid, client)
            except Exception as e:
                await client.disconnect()
                setup_state.pop(uid, None)
                await event.reply(f"❌ Password 2FA salah: {e}\n\nCoba /setup ulang.")

    async def _finish_setup(event, uid, client):
        string_session = client.session.save()
        await db.save_session(string_session)
        await client.disconnect()
        setup_state.pop(uid, None)
        await event.reply(
            "✅ *Setup berhasil! Akun kamu sudah terhubung.*\n\n"
            "⚠️ Jangan logout dari sesi Telegram ini.\n\n"
            "🤖 Auto-reply AI sudah aktif!\n"
            "Gunakan command via **Saved Messages** kamu.",
            parse_mode="md"
        )
        await start_user_client()


async def main():
    global ai, bot_client

    await db.init()
    print("✅ Database siap.")

    ai = AIHandler(db)
    print("✅ AI Handler siap.")

    # ── Bot client (hanya untuk /setup, tidak ada polling conflict)
    bot_client = TelegramClient("bot", config.API_ID, config.API_HASH)
    await bot_client.start(bot_token=config.BOT_TOKEN)
    register_bot_events()
    print("✅ Bot client siap.")

    # ── User client (kalau session sudah ada)
    await start_user_client()

    print("🚀 Semua siap! Kirim /setup ke bot untuk login.")
    await asyncio.gather(
        bot_client.run_until_disconnected(),
        user_client.run_until_disconnected() if user_client else asyncio.sleep(0),
    )


if __name__ == "__main__":
    asyncio.run(main())
