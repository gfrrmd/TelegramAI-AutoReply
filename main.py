import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from config import config
from database import Database
from ai_handler import AIHandler
from auth import register_auth_handlers

db = Database()
ai = AIHandler()

# Bot PTB untuk handle command setup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters
from auth import (
    cmd_setup, cmd_cancel, setup_phone, setup_code, setup_password,
    PHONE_STEP, CODE_STEP, PASSWORD_STEP
)

last_active: float = time.time()
pending: set = set()
user_client: TelegramClient = None


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


async def main():
    await db.init()
    print("✅ Database siap.")

    # Start user client kalau sudah ada session
    await start_user_client()

    # Build bot PTB
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Conversation handler untuk /setup
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("setup", cmd_setup),
        ],
        states={
            PHONE_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_phone)],
            CODE_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_code)],
            PASSWORD_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_password)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )
    app.add_handler(conv_handler)

    # Command handler lainnya (via Saved Messages user client)
    # Dihandle lewat user_client events di register_user_events()

    print("🤖 Bot berjalan. Kirim /setup ke bot untuk login.")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
