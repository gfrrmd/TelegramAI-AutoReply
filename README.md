# 🤖 TelegramAI AutoReply

Auto-reply AI untuk akun Telegram menggunakan **Telethon** + **Google Gemini**. Bot membalas pesan masuk atas nama akunmu saat kamu sedang tidak aktif — login via bot (OTP flow), session & log tersimpan di **PostgreSQL Railway**.

---

## ✨ Fitur

- 🤖 **Auto-reply AI** — Gemini 2.0 Flash balas pesan atas nama akunmu
- 🧠 **Konteks percakapan** — AI ingat riwayat chat tiap sender
- ✏️ **Persona global** — ubah karakter/gaya balasan AI untuk semua orang
- 💚 **Persona khusus per orang** — beda prompt untuk orang tertentu (gebetan mode 😄)
- ⏱️ **Idle detection** — hanya aktif saat kamu tidak aktif (configurable)
- ⏳ **Reply delay** — jeda alami sebelum balas agar tidak terlihat seperti bot
- 📢 **Log ke channel Telegram** — notifikasi real-time setiap kali bot auto-reply
- 📋 **Log via Saved Messages** — lihat 10 log terakhir langsung dari chat
- 🔒 **Whitelist & Blacklist** — kontrol siapa yang dapat auto-reply
- 🗑️ **Clear history** — hapus riwayat percakapan per user
- 🔐 **Login via bot** — setup akun lewat OTP langsung di bot (tidak perlu lokal)
- ✅ **Private chat only** — tidak aktif di grup atau channel
- ☁️ **Deploy-ready** — siap deploy di Railway dengan PostgreSQL

---

## 🚀 Cara Deploy ke Railway

### Langkah 1 — Siapkan semua credential

**A. Buat bot di @BotFather**
- Buka [@BotFather](https://t.me/BotFather) → `/newbot`
- Ikuti instruksi → catat `BOT_TOKEN`

**B. Dapatkan Telegram API**
- Buka [my.telegram.org](https://my.telegram.org) → login
- Pilih **API Development Tools** → buat app
- Catat `API_ID` dan `API_HASH`

**C. Cek Owner ID kamu**
- Forward pesan apa saja ke [@userinfobot](https://t.me/userinfobot)
- Catat angka `Id` yang muncul → isi ke `OWNER_ID`

**D. Dapatkan Gemini API Key**
- Buka [aistudio.google.com](https://aistudio.google.com)
- Klik **Get API Key** → Create API Key
- Pilih model `gemini-2.0-flash` (gratis, 1500 req/hari)

**E. Siapkan Log Channel (opsional)**
- Buat channel privat di Telegram (contoh: "AI Reply Logs")
- Tambahkan **bot kamu** sebagai admin channel (izin: post message)
- Forward pesan dari channel ke [@userinfobot](https://t.me/userinfobot) → catat ID (format: `-1001234567890`)

---

### Langkah 2 — Deploy di Railway

1. Buka [railway.app](https://railway.app) → **New Project**
2. Pilih **Deploy from GitHub repo** → pilih repo `TelegramAI-AutoReply`
3. Klik **Add Service** → pilih **PostgreSQL** → Railway otomatis sediakan database
4. Buka service bot → tab **Variables** → isi semua env variable:

| Variable | Nilai |
|---|---|
| `API_ID` | dari my.telegram.org |
| `API_HASH` | dari my.telegram.org |
| `BOT_TOKEN` | dari @BotFather |
| `OWNER_ID` | Telegram user ID kamu |
| `GEMINI_API_KEY` | dari aistudio.google.com |
| `LOG_CHANNEL` | ID channel log (opsional) |

5. Di tab **Variables**, klik **Add Reference** → pilih service PostgreSQL → pilih `DATABASE_URL` (otomatis ter-link)
6. Klik **Deploy** → tunggu build selesai ✅

---

### Langkah 3 — Login via Bot

Setelah deploy berhasil:
1. Buka bot kamu di Telegram
2. Kirim `/setup`
3. Bot akan minta **nomor HP** → kirim nomor format `+6281xxxxxxxxx`
4. Bot kirim OTP ke Telegram kamu → kirim kode dengan spasi: `1 2 3 4 5`
5. Kalau ada **2FA** → bot minta password → kirim password 2FA
6. Selesai! ✅ Bot langsung aktif memantau pesanmu

> ⚠️ **Penting:** Jangan logout dari sesi Telegram yang dipakai untuk setup. Kalau logout, perlu `/setup` ulang.

---

## 🎮 Commands

### Di bot (setup awal)

| Command | Fungsi |
|---|---|
| `/setup` | Login akun Telegram ke bot via OTP |
| `/cancel` | Batalkan proses setup |

### Di Saved Messages (setelah setup)

**🔧 Auto-Reply**
| Command | Fungsi |
|---|---|
| `/autoreply on` | Aktifkan auto-reply |
| `/autoreply off` | Nonaktifkan auto-reply |
| `/status` | Cek status, idle time & log channel |

**🧠 Persona Global**
| Command | Fungsi |
|---|---|
| `/setpersona <teks>` | Ubah persona default AI untuk semua orang |

**💚 Persona Khusus per Orang**
| Command | Fungsi |
|---|---|
| `/setuserpersona <user_id> <prompt>` | Set persona khusus untuk 1 orang |
| `/deluserpersona <user_id>` | Hapus persona khusus (kembali ke global) |
| `/listpersona` | Lihat semua persona khusus yang aktif |

**📋 Riwayat & Log**
| Command | Fungsi |
|---|---|
| `/clearhistory <user_id>` | Hapus riwayat chat dengan user tertentu |
| `/logs` | Lihat 10 log auto-reply terakhir |
| `/help` | Tampilkan semua command |

> 💡 Cara cek user ID seseorang: suruh mereka forward pesan ke [@userinfobot](https://t.me/userinfobot), atau lihat dari `/logs` setelah mereka DM kamu.

---

## ⚙️ Environment Variables

| Variable | Wajib | Default | Keterangan |
|---|---|---|---|
| `API_ID` | ✅ | — | Telegram API ID dari my.telegram.org |
| `API_HASH` | ✅ | — | Telegram API Hash dari my.telegram.org |
| `BOT_TOKEN` | ✅ | — | Token bot dari @BotFather |
| `OWNER_ID` | ✅ | — | Telegram user ID kamu |
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API Key |
| `DATABASE_URL` | ✅ | — | PostgreSQL Railway (auto dari link service) |
| `LOG_CHANNEL` | ❌ | kosong | ID atau username channel log |
| `GEMINI_MODEL` | ❌ | `gemini-2.0-flash` | Model Gemini yang dipakai |
| `IDLE_TIMEOUT` | ❌ | `300` | Detik idle sebelum bot aktif (5 menit) |
| `REPLY_DELAY` | ❌ | `3` | Jeda detik sebelum balas |
| `HISTORY_LIMIT` | ❌ | `10` | Jumlah riwayat pesan yang dikasih ke AI |
| `WHITELIST_ENABLED` | ❌ | `false` | `true` = hanya balas kontak di whitelist |
| `WHITELIST_IDS` | ❌ | kosong | ID yang di-whitelist, pisah koma |
| `BLACKLIST_IDS` | ❌ | kosong | ID yang di-blacklist, pisah koma |

---

## 🗄️ Struktur Database

```
settings          → konfigurasi (autoreply status, persona global, string session)
chat_history      → riwayat percakapan per sender (untuk konteks AI)
autoreply_logs    → log semua balasan otomatis
user_personas     → persona khusus per user
```

---

## 📁 Struktur Project

```
TelegramAI-AutoReply/
├── main.py           # Entry point: PTB bot + Telethon user client + commands
├── auth.py           # OTP login flow via bot
├── config.py         # Konfigurasi dari environment variable
├── database.py       # Operasi PostgreSQL (asyncpg)
├── ai_handler.py     # Integrasi Google Gemini + persona logic
├── requirements.txt
├── Procfile
├── railway.toml
├── .env.example
└── README.md
```

---

## 📝 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
