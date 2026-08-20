# 🤖 TelegramAI AutoReply

Auto-reply AI untuk akun Telegram menggunakan **Telethon** + **Google Gemini**. Bot membalas pesan masuk atas nama akunmu saat kamu sedang tidak aktif, dengan login via bot (OTP flow) dan session tersimpan di **PostgreSQL Railway**.

---

## ✨ Fitur

- 🤖 **Auto-reply AI** — Gemini 2.0 Flash balas pesan atas nama akunmu
- 🧠 **Konteks percakapan** — AI ingat riwayat chat tiap sender
- ✏️ **Persona kustom** — ubah karakter/gaya balasan AI
- ⏱️ **Idle detection** — hanya aktif saat kamu tidak aktif (configurable)
- ⏳ **Reply delay** — jeda alami sebelum balas
- 📋 **Log auto-reply** — lihat log balasan dari Saved Messages
- 🔒 **Whitelist & Blacklist** — kontrol siapa yang dapat auto-reply
- 🗑️ **Clear history** — hapus riwayat percakapan per user
- 🔐 **Login via bot** — setup akun lewat OTP langsung di bot (tidak perlu lokal)
- ☁️ **Deploy-ready** — siap deploy di Railway dengan PostgreSQL

---

## 🚀 Deploy ke Railway

### 1. Buat Bot di @BotFather
- Buka [@BotFather](https://t.me/BotFather) → `/newbot`
- Catat `BOT_TOKEN`

### 2. Dapatkan Telegram API Credentials
- Buka [my.telegram.org](https://my.telegram.org)
- Login → **API Development Tools**
- Catat `API_ID` dan `API_HASH`

### 3. Cek Owner ID kamu
- Forward pesan ke [@userinfobot](https://t.me/userinfobot)
- Catat `Id` yang muncul → isi ke `OWNER_ID`

### 4. Dapatkan Gemini API Key
- Buka [aistudio.google.com](https://aistudio.google.com)
- **Get API Key** → pilih model `gemini-2.0-flash`

### 5. Setup Railway
1. Buat project baru di [railway.app](https://railway.app)
2. Tambahkan **PostgreSQL** dari menu Add Service
3. Deploy repo ini via GitHub
4. Isi semua environment variable dari `.env.example`
5. `DATABASE_URL` otomatis tersedia dari Railway PostgreSQL

### 6. Login via Bot
Setelah deploy, buka bot kamu di Telegram → kirim `/setup` → ikuti langkah-langkahnya.

---

## 🎮 Commands

### Di bot (untuk setup awal)
| Command | Fungsi |
|---|---|
| `/setup` | Login akun Telegram ke bot |
| `/cancel` | Batalkan proses setup |

### Di Saved Messages (setelah setup)
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
| `BOT_TOKEN` | ✅ | Token bot dari @BotFather |
| `OWNER_ID` | ✅ | Telegram user ID kamu |
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
settings          → konfigurasi (status, persona, string_session)
chat_history      → riwayat percakapan per sender
autoreply_logs    → log semua balasan otomatis
```

---

## 📁 Struktur Project

```
TelegramAI-AutoReply/
├── main.py           # Entry point, PTB bot + Telethon user client
├── auth.py           # OTP login flow via bot
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
