import asyncio
import time
from datetime import datetime, timezone, timedelta

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)

from config import config
from database import Database
from ai_handler import AIHandler

WIB = timezone(timedelta(hours=7))

# ── Globals ─────────────────────────────────────────
db = Database()
ai: AIHandler = None
bot_client: TelegramClient = None   # bot token  → handle /setup
user_client: TelegramClient = None  # userbot    → auto-reply + commands
my_id: int = None                   # di-cache saat user_client login
last_active: float = time.time()
pending: set = set()

# state mesin /setup per user
_setup_state: dict = {}


# ── Helper ────────────────────────────────────────
async def _send_log(sender_id, sender_name, incoming, reply):
    if not config.LOG_CHANNEL:
        return
    try:
        now = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
        persona = await db.get_user_persona(sender_id)
        label = "💚 Persona khusus" if persona else "🌏 Persona global"
        text = (
            f"🤖 **Auto-Reply Terkirim**\n"
            f"────────────────────\n"
            f"👤 **Dari:** {sender_name} (`{sender_id}`)\n"
            f"🕐 **Waktu:** {now}\n"
            f"{label}\n"
            f"────────────────────\n"
            f"💬 **Pesan masuk:**\n{incoming}\n\n"
            f"🤖 **Balasan AI:**\n{reply}"
        )
        await bot_client.send_message(int(config.LOG_CHANNEL), text)
    except Exception as e:
        print(f"[Log] Gagal: {e}")


# ── User client (userbot) ──────────────────────────
async def start_user_client():
    global user_client, my_id
    session_str = await db.get_session()
    if not session_str:
        print("⚠️ Belum ada session. Kirim /setup ke bot.")
        return
    if user_client and user_client.is_connected():
        await user_client.disconnect()
    user_client = TelegramClient(
        StringSession(session_str), config.API_ID, config.API_HASH
    )
    await user_client.connect()
    if not await user_client.is_user_authorized():
        print("⚠️ Session tidak valid. /setup ulang.")
        user_client = None
        return
    me = await user_client.get_me()
    my_id = me.id
    print(f"✅ Userbot: {me.first_name} (@{me.username}) id={my_id}")
    _register_userbot_events()
    asyncio.ensure_future(user_client.run_until_disconnected())


def _register_userbot_events():

    @user_client.on(events.NewMessage(outgoing=True))
    async def _track_active(event):
        global last_active
        last_active = time.time()

    @user_client.on(events.NewMessage(incoming=True))
    async def _auto_reply(event):
        if not event.is_private:
            return
        sender = await event.get_sender()
        if not isinstance(sender, User) or sender.bot:
            return

        sid = sender.id
        sname = sender.first_name or "Someone"

        if config.WHITELIST_ENABLED and str(sid) not in config.WHITELIST_IDS:
            return
        if str(sid) in config.BLACKLIST_IDS:
            return
        if not await db.get_autoreply_status():
            return
        if (time.time() - last_active) < config.IDLE_TIMEOUT:
            return
        if sid in pending:
            return

        pending.add(sid)
        try:
            await db.save_message(sid, "user", event.raw_text)
            history = await db.get_history(sid, limit=config.HISTORY_LIMIT)
            reply = await ai.generate_reply(
                sender_id=sid, sender_name=sname,
                history=history, new_message=event.raw_text
            )
            if reply:
                await asyncio.sleep(config.REPLY_DELAY)
                await event.reply(reply)
                await db.save_message(sid, "assistant", reply)
                await db.log_autoreply(sid, sname, event.raw_text, reply)
                await _send_log(sid, sname, event.raw_text, reply)
        finally:
            pending.discard(sid)

    # ── Commands di Saved Messages (outgoing) ─────────────

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/autoreply (on|off)$"))
    async def _cmd_autoreply(event):
        if event.chat_id != my_id:
            return
        on = event.pattern_match.group(1) == "on"
        await db.set_autoreply_status(on)
        await event.reply(f"✅ Auto-reply {'diaktifkan' if on else 'dinonaktifkan'}.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/status$"))
    async def _cmd_status(event):
        if event.chat_id != my_id:
            return
        active = await db.get_autoreply_status()
        idle = int(time.time() - last_active)
        await event.reply(
            f"📊 **Status**\n"
            f"• Auto-reply: {'🟢 Aktif' if active else '🔴 Nonaktif'}\n"
            f"• Idle: {idle}s / timeout: {config.IDLE_TIMEOUT}s\n"
            f"• Log channel: `{config.LOG_CHANNEL or 'nonaktif'}`"
        )

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/setpersona (.+)$"))
    async def _cmd_setpersona(event):
        if event.chat_id != my_id:
            return
        p = event.pattern_match.group(1)
        await db.set_persona(p)
        await event.reply(f"✅ Persona global diubah.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/setuserpersona (\d+) (.+)$"))
    async def _cmd_setuserpersona(event):
        if event.chat_id != my_id:
            return
        sid = int(event.pattern_match.group(1))
        p = event.pattern_match.group(2)
        try:
            target = await user_client.get_entity(sid)
            name = target.first_name or str(sid)
        except Exception:
            name = str(sid)
        await db.set_user_persona(sid, name, p)
        await event.reply(f"💚 Persona khusus disimpan untuk **{name}**.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/deluserpersona (\d+)$"))
    async def _cmd_deluserpersona(event):
        if event.chat_id != my_id:
            return
        sid = int(event.pattern_match.group(1))
        ok = await db.delete_user_persona(sid)
        await event.reply(
            f"✅ Persona untuk `{sid}` dihapus." if ok
            else f"❌ Tidak ada persona untuk `{sid}`."
        )

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/listpersona$"))
    async def _cmd_listpersona(event):
        if event.chat_id != my_id:
            return
        rows = await db.list_user_personas()
        if not rows:
            await event.reply("📭 Belum ada persona khusus.")
            return
        txt = "💚 **Persona Khusus:**\n\n"
        for r in rows:
            txt += f"👤 **{r['sender_name']}** (`{r['sender_id']}`)\n{r['persona'][:100]}\n\n"
        await event.reply(txt)

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/clearhistory (\d+)$"))
    async def _cmd_clear(event):
        if event.chat_id != my_id:
            return
        uid = int(event.pattern_match.group(1))
        await db.clear_history(uid)
        await event.reply(f"🗑️ Riwayat `{uid}` dihapus.")

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/logs$"))
    async def _cmd_logs(event):
        if event.chat_id != my_id:
            return
        logs = await db.get_logs(limit=10)
        if not logs:
            await event.reply("📭 Belum ada log.")
            return
        txt = "📋 **10 Log Terakhir:**\n\n"
        for l in logs:
            txt += (
                f"👤 {l['sender_name']} (`{l['sender_id']}`)\n"
                f"💬 {l['incoming'][:80]}\n"
                f"🤖 {l['reply'][:80]}\n"
                f"🕐 {l['created_at']}\n\n"
            )
        await event.reply(txt)

    @user_client.on(events.NewMessage(outgoing=True, pattern=r"^/help$"))
    async def _cmd_help(event):
        if event.chat_id != my_id:
            return
        await event.reply(
            "🤖 **TelegramAI AutoReply — Commands**\n"
            "(Kirim di **Saved Messages**)\n\n"
            "`/autoreply on|off` — aktifkan/nonaktifkan\n"
            "`/status` — cek status\n"
            "`/setpersona <teks>` — persona global\n"
            "`/setuserpersona <id> <prompt>` — persona khusus\n"
            "`/deluserpersona <id>` — hapus persona khusus\n"
            "`/listpersona` — daftar persona khusus\n"
            "`/clearhistory <id>` — hapus riwayat\n"
            "`/logs` — 10 log terakhir"
        )


# ── Bot client (/setup handler) ──────────────────────
def _register_bot_events():

    @bot_client.on(events.NewMessage(pattern=r"^/start$"))
    async def _start(event):
        if event.sender_id != config.OWNER_ID:
            return
        await event.reply(
            "🤖 **TelegramAI AutoReply**\n"
            "Kirim /setup untuk menghubungkan akun Telegram kamu."
        )

    @bot_client.on(events.NewMessage(pattern=r"^/setup$"))
    async def _setup(event):
        if event.sender_id != config.OWNER_ID:
            await event.reply("❌ Kamu tidak punya akses.")
            return
        _setup_state[event.sender_id] = {"step": "phone", "client": None}
        await event.reply(
            "🤖 *Setup TelegramAI AutoReply*\n\n"
            "Langkah 1/3 — Nomor HP\n"
            "Masukkan nomor HP kamu (contoh: `+6281234567890`)\n"
            "Kirim /cancel untuk batal.",
            parse_mode="md"
        )

    @bot_client.on(events.NewMessage(pattern=r"^/cancel$"))
    async def _cancel(event):
        if event.sender_id != config.OWNER_ID:
            return
        st = _setup_state.pop(event.sender_id, {})
        c = st.get("client")
        if c and c.is_connected():
            await c.disconnect()
        await event.reply("❌ Setup dibatalkan.")

    @bot_client.on(events.NewMessage)
    async def _text(event):
        if event.sender_id != config.OWNER_ID:
            return
        if not event.text or event.text.startswith("/"):
            return
        uid = event.sender_id
        st = _setup_state.get(uid)
        if not st:
            return

        if st["step"] == "phone":
            phone = event.text.strip()
            tmp = TelegramClient(StringSession(), config.API_ID, config.API_HASH)
            await tmp.connect()
            try:
                result = await tmp.send_code_request(phone)
                st.update({"step": "code", "phone": phone,
                           "hash": result.phone_code_hash, "client": tmp})
                await event.reply(
                    "📨 Kode OTP dikirim!\n\n"
                    "Langkah 2/3 — Kode OTP\n"
                    "Ketik kode dengan spasi: `1 2 3 4 5`\n"
                    "Kirim /cancel untuk batal.",
                    parse_mode="md"
                )
            except Exception as e:
                await tmp.disconnect()
                _setup_state.pop(uid, None)
                await event.reply(f"❌ Gagal kirim OTP: {e}\n\nCoba /setup ulang.")

        elif st["step"] == "code":
            code = event.text.strip().replace(" ", "")
            tmp = st["client"]
            try:
                await tmp.sign_in(st["phone"], code, phone_code_hash=st["hash"])
                await _finish_setup(event, uid, tmp)
            except SessionPasswordNeededError:
                st["step"] = "password"
                await event.reply(
                    "🔐 Akun 2FA aktif.\n\n"
                    "Langkah 3/3 — Password 2FA\n"
                    "Masukkan password 2FA kamu.\n"
                    "Kirim /cancel untuk batal."
                )
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                await tmp.disconnect()
                _setup_state.pop(uid, None)
                await event.reply("❌ Kode OTP salah/kadaluarsa. Coba /setup ulang.")
            except Exception as e:
                await tmp.disconnect()
                _setup_state.pop(uid, None)
                await event.reply(f"❌ Error: {e}\n\nCoba /setup ulang.")

        elif st["step"] == "password":
            tmp = st["client"]
            try:
                await tmp.sign_in(password=event.text.strip())
                await _finish_setup(event, uid, tmp)
            except Exception as e:
                await tmp.disconnect()
                _setup_state.pop(uid, None)
                await event.reply(f"❌ Password 2FA salah: {e}\n\nCoba /setup ulang.")


async def _finish_setup(event, uid: int, tmp: TelegramClient):
    string_session = tmp.session.save()
    await db.save_session(string_session)
    await tmp.disconnect()
    _setup_state.pop(uid, None)
    await event.reply(
        "✅ *Setup berhasil!*\n\n"
        "⚠️ Jangan logout dari sesi Telegram ini.\n\n"
        "🤖 Auto-reply AI aktif!\n"
        "Gunakan command di **Saved Messages** kamu.\n"
        "Ketik `/help` di Saved Messages untuk daftar command.",
        parse_mode="md"
    )
    await start_user_client()


# ── Entry point ──────────────────────────────────
async def main():
    global ai, bot_client

    await db.init()
    print("✅ Database siap.")

    ai = AIHandler(db)
    print("✅ AI Handler siap.")

    bot_client = TelegramClient(StringSession(), config.API_ID, config.API_HASH)
    await bot_client.start(bot_token=config.BOT_TOKEN)
    _register_bot_events()
    print("✅ Bot client siap.")

    await start_user_client()

    print("🚀 Semua siap! Kirim /setup ke bot untuk login pertama kali.")

    # Jalankan keduanya; kalau user_client None, hanya bot_client yang jalan
    tasks = [bot_client.run_until_disconnected()]
    if user_client is not None:
        tasks.append(user_client.run_until_disconnected())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
