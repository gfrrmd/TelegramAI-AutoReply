import re
import google.generativeai as genai
from config import config

genai.configure(api_key=config.GEMINI_API_KEY)

DEFAULT_PERSONA = (
    "Kamu adalah asisten pribadi Rama. "
    "Tugasmu membalas pesan yang masuk ke HP Rama saat dia sedang sibuk atau tidak bisa membalas. "
    "Kamu mewakili Rama, jadi balas seolah-olah kamu adalah Rama sendiri (pakai kata 'aku'). "
    "Jangan pernah bilang kamu adalah AI atau bot."
)


def _clean(text: str) -> str:
    # Hapus zero-width & invisible unicode
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]', '', text)
    # Hapus markdown
    text = re.sub(r'[*_`~]', '', text)
    # Smart quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # Dash
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    # Spasi & baris berlebih
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class AIHandler:
    def __init__(self, db):
        self._db = db
        print(f"[AIHandler] Init dengan model: {config.GEMINI_MODEL}")

    async def generate_reply(
        self,
        sender_id: int,
        sender_name: str,
        history: list,
        new_message: str
    ) -> str | None:
        print(f"[AIHandler] Memproses pesan dari {sender_name} ({sender_id}): {new_message[:50]}")
        try:
            user_persona = await self._db.get_user_persona(sender_id)
            global_persona = await self._db.get_persona()

            # Kalau global_persona kosong/default, pakai DEFAULT_PERSONA
            persona_text = user_persona or global_persona or DEFAULT_PERSONA

            base_rules = (
                "ATURAN WAJIB:\n"
                "- Balas HANYA 1-2 kalimat singkat, jangan panjang.\n"
                "- Pastikan kalimat SELALU selesai, jangan terpotong di tengah.\n"
                "- Gunakan bahasa Indonesia informal/santai (seperti chat biasa).\n"
                "- Jangan pakai markdown, bullet, simbol *, _, `, ~.\n"
                "- Jangan pakai emoji berlebihan.\n"
                "- Jangan pernah mengaku sebagai AI atau bot."
            )

            system_prompt = (
                f"{persona_text}\n\n"
                f"Kamu sedang membalas pesan dari {sender_name}.\n\n"
                f"{base_rules}"
            )

            temperature = 0.8 if user_persona else 0.7
            if user_persona:
                print(f"[AIHandler] Pakai persona khusus untuk {sender_name}")
            else:
                print(f"[AIHandler] Pakai persona {'global' if global_persona else 'default'}")

            model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=system_prompt
            )

            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})
            contents.append({"role": "user", "parts": [new_message]})

            response = model.generate_content(
                contents,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=80,   # cukup untuk 1-2 kalimat, tidak terpotong
                    temperature=temperature,
                )
            )

            raw = response.text.strip() if response.text else None
            if not raw:
                print("[AIHandler] Gemini tidak menghasilkan teks")
                return None

            result = _clean(raw)
            print(f"[AIHandler] Balasan: {result[:80]}")
            return result

        except Exception as e:
            print(f"[AIHandler] ERROR: {e}")
            return None
