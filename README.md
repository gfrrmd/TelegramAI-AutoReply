# 🤖 TelegramAI AutoReply

Auto-reply AI untuk akun Telegram menggunakan **Telethon** + **Google Gemini**. Bot membalas pesan masuk atas nama akunmu saat kamu sedang tidak aktif, dengan konteks percakapan yang tersimpan di **PostgreSQL Railway**.

---

## ✨ Fitur

- 🤖 **Auto-reply AI** — Gemini 2.0 Flash balas pesan atas nama akunmu
- 🧠 **Konteks percakapan** — AI ingat riwayat chat tiap sender
- ✏️ **Persona kustom** — ubah karakter/gaya balasan AI
- ⏱️ **Idle detection** — hanya aktif saat kamu tidak aktif (configurable)
- ⏳ **Reply delay** — jeda alami sebelum balas agar tidak terlihat seperti bot
- 📋 **Log auto-reply** — lihat log balasan langsung dari Saved Messages
- 🔒 **Whitelist & Blacklist** — kontrol siapa yang boleh dapat auto-reply
- 🗑️ **Clear history** — hapus riwayat percakapan per user
- ☁️ **Deploy-ready** — siap deploy di Railway dengan PostgreSQL

---

## 🚀 Deploy ke Railway

### 1. Fork & Clone
```bash
git clone https://github.com/gfrrmd/TelegramAI-AutoReply.git
cd TelegramAI-AutoReply
```

### 2. Dapatkan Telegram API Credentials
- Buka [my.telegram.org](https://my.telegram.org)
- Login → **API Development Tools**
- Catat `API_ID` dan `API_HASH`

### 3. Dapatkan Gemini API Key
- Buka [aistudio.google.com](https://aistudio.google.com)
- Buat project → **Get API Key** → pilih model `gemini-2.0-flash`

### 4. Setup Railway
1. Buat project baru di [railway.app](https://railway.app)
2. Tambahkan **PostgreSQL** dari menu Add Service
3. Deploy repo ini via GitHub
4. Isi semua environment variable dari `.env.example`
5. Variabel `DATABASE_URL` otomatis tersedia dari Railway PostgreSQL

### 5. Generate String Session (untuk Railway)
Karena Railway tidak bisa interaktif, generate session dulu di lokal:
```bash
pip install telethon
python -c "
import asyncio
from telethon import TelegramClient
async def main():
    client = TelegramClient('session/account', API_ID, API_HASH)
    await client.start()
    print('Session tersimpan di session/account.session')
asyncio.run(main())
"
```
Lalu upload file `session/account.session` ke Railway via volume, atau gunakan [Telegram-String-Session-Bot](https://github.com/gfrrmd/Telegram-String-Session-Bot) milikmu sendiri.

---

## 🎮 Commands

Kirim command ini ke **Saved Messages** kamu di Telegram:

| Command | Fungsi |
|---|---|
| `/autoreply on` | Aktifkan auto-reply |
| `/autoreply off` | Nonaktifkan auto-reply |
| `/status` | Cek status & idle time |
| `/setpersona <teks>` | Ubah persona/gaya balasan AI |
| `/clearhistory <user_id>` | Hapus riwayat chat dengan user |
| `/logs` | Lihat 10 log auto-reply terakhir |
| `/help` | Tampilkan daftar command |

---

## ⚙️ Environment Variables

| Variable | Wajib | Keterangan |
|---|---|---|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `PHONE_NUMBER` | ✅ | Nomor HP format +62 |
| `GEMINI_API_KEY` | ✅ | Google Gemini API Key |
| `DATABASE_URL` | ✅ | PostgreSQL Railway |
| `IDLE_TIMEOUT` | ❌ | Detik idle (default: 300) |
| `REPLY_DELAY` | ❌ | Jeda balas detik (default: 3) |
| `HISTORY_LIMIT` | ❌ | Limit riwayat AI (default: 10) |
| `WHITELIST_ENABLED` | ❌ | Aktifkan whitelist (default: false) |
| `WHITELIST_IDS` | ❌ | ID yang di-whitelist |
| `BLACKLIST_IDS` | ❌ | ID yang di-blacklist |

---

## 🗄️ Struktur Database

```
settings          → konfigurasi (status, persona)
chat_history      → riwayat percakapan per sender
autoreply_logs    → log semua balasan otomatis
```

---

## 📁 Struktur Project

```
TelegramAI-AutoReply/
├── main.py           # Entry point, event handler Telethon
├── config.py         # Konfigurasi dari environment variable
├── database.py       # Operasi PostgreSQL (asyncpg)
├── ai_handler.py     # Integrasi Google Gemini
├── requirements.txt
├── Procfile
├── railway.toml
├── .env.example
└── README.md
```

---

## 📝 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
