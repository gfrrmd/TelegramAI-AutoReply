import re
import google.generativeai as genai
from config import config

genai.configure(api_key=config.GEMINI_API_KEY)


def _clean(text: str) -> str:
    """Bersihkan karakter aneh, markdown, dan zero-width chars dari response AI."""
    # Hapus zero-width & invisible unicode chars
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]', '', text)
    # Hapus markdown bold/italic/code
    text = re.sub(r'[*_`~]', '', text)
    # Ganti smart quotes dengan quote biasa
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # Ganti em dash & en dash dengan strip biasa
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    # Hapus spasi berlebih
    text = re.sub(r' +', ' ', text)
    # Hapus baris kosong berlebih
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

            base_rules = (
                "PENTING: Balas HANYA dengan teks biasa. "
                "Jangan gunakan markdown, bold, italic, bullet, atau simbol apapun. "
                "Jangan gunakan tanda bintang (*), underscore (_), backtick (`), atau tilde (~). "
                "Tulis seperti orang chat biasa di WhatsApp."
            )

            if user_persona:
                system_prompt = (
                    f"{user_persona}\n\n"
                    f"Kamu sedang membalas pesan dari {sender_name}. "
                    f"Balas dengan natural, tidak terlihat seperti bot.\n\n"
                    f"{base_rules}"
                )
                temperature = 0.8
                print(f"[AIHandler] Pakai persona khusus untuk {sender_name}")
            else:
                system_prompt = (
                    f"{global_persona}\n\n"
                    f"Kamu sedang membalas pesan dari {sender_name}. "
                    f"Balas singkat, natural, maksimal 2-3 kalimat pendek.\n\n"
                    f"{base_rules}"
                )
                temperature = 0.7
                print(f"[AIHandler] Pakai persona global")

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
                    max_output_tokens=200,
                    temperature=temperature,
                )
            )

            raw = response.text.strip() if response.text else None
            if not raw:
                print(f"[AIHandler] Gemini tidak menghasilkan teks")
                return None

            result = _clean(raw)
            print(f"[AIHandler] Balasan: {result[:80]}")
            return result

        except Exception as e:
            print(f"[AIHandler] ERROR: {e}")
            return None
