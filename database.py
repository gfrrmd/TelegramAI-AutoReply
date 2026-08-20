import asyncpg
from config import config


class Database:
    def __init__(self):
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(config.DATABASE_URL)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS autoreply_logs (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT NOT NULL,
                    sender_name TEXT,
                    incoming TEXT,
                    reply TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS user_personas (
                    sender_id BIGINT PRIMARY KEY,
                    sender_name TEXT,
                    persona TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
        await self._set_default("autoreply_status", "true")
        await self._set_default("persona", "Kamu adalah asisten pribadi yang ramah, sopan, dan membalas pesan dengan singkat dan natural seperti orang Indonesia pada umumnya.")

    async def _set_default(self, key: str, value: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING;
            """, key, value)

    # ── Session ────────────────────────────────────────────────────────────
    async def save_session(self, session_str: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ('string_session', $1)
                ON CONFLICT (key) DO UPDATE SET value = $1;
            """, session_str)

    async def get_session(self) -> str | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = 'string_session'")
            return row["value"] if row else None

    # ── Auto-reply status ──────────────────────────────────────────────────
    async def get_autoreply_status(self) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = 'autoreply_status'")
            return row["value"] == "true" if row else True

    async def set_autoreply_status(self, status: bool):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ('autoreply_status', $1)
                ON CONFLICT (key) DO UPDATE SET value = $1;
            """, str(status).lower())

    # ── Global Persona ──────────────────────────────────────────────────────
    async def get_persona(self) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = 'persona'")
            return row["value"] if row else ""

    async def set_persona(self, persona: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ('persona', $1)
                ON CONFLICT (key) DO UPDATE SET value = $1;
            """, persona)

    # ── Per-user Persona ────────────────────────────────────────────────────
    async def set_user_persona(self, sender_id: int, sender_name: str, persona: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_personas (sender_id, sender_name, persona, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (sender_id) DO UPDATE SET persona = $3, sender_name = $2, updated_at = NOW();
            """, sender_id, sender_name, persona)

    async def get_user_persona(self, sender_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT persona FROM user_personas WHERE sender_id = $1", sender_id
            )
            return row["persona"] if row else None

    async def delete_user_persona(self, sender_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM user_personas WHERE sender_id = $1", sender_id
            )
            return result == "DELETE 1"

    async def list_user_personas(self) -> list:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sender_id, sender_name, persona, updated_at
                FROM user_personas ORDER BY updated_at DESC;
            """)
            return [dict(r) for r in rows]

    # ── Chat history ───────────────────────────────────────────────────────
    async def save_message(self, sender_id: int, role: str, content: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_history (sender_id, role, content) VALUES ($1, $2, $3);
            """, sender_id, role, content)

    async def get_history(self, sender_id: int, limit: int = 10) -> list:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT role, content FROM chat_history
                WHERE sender_id = $1
                ORDER BY created_at DESC
                LIMIT $2;
            """, sender_id, limit)
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def clear_history(self, sender_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_history WHERE sender_id = $1;", sender_id)

    # ── Logs ───────────────────────────────────────────────────────────────
    async def log_autoreply(self, sender_id: int, sender_name: str, incoming: str, reply: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO autoreply_logs (sender_id, sender_name, incoming, reply)
                VALUES ($1, $2, $3, $4);
            """, sender_id, sender_name, incoming, reply)

    async def get_logs(self, limit: int = 10) -> list:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sender_id, sender_name, incoming, reply, created_at
                FROM autoreply_logs
                ORDER BY created_at DESC
                LIMIT $1;
            """, limit)
            return [dict(r) for r in rows]
