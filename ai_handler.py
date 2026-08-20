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
    """Bersihkan karakter aneh dan markdown."""
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]', '', text)
    text = re.sub(r'[*_`~]', '', text)
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _trim_to_sentence(text: str) -> str:
    """Potong teks sampai tanda baca penutup kalimat terakhir (. ! ?)."""
    # Cari posisi tanda baca penutup kalimat terakhir
    match = re.search(r'[.!?][^.!?]*$', text)
    if match:
        # Ambil sampai tanda baca itu (inklusif)
        end = match.start() + 1
        return text[:end].strip()
    # Kalau tidak ada tanda baca sama sekali, kembalikan apa adanya
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

            persona_text = user_persona or global_persona or DEFAULT_PERSONA

            base_rules = (
                "ATURAN WAJIB:\n"
                "- Balas maksimal 2-3 kalimat, tidak lebih.\n"
                "- Setiap kalimat HARUS diakhiri tanda titik (.), tanda seru (!), atau tanda tanya (?).\n"
                "- Jangan pernah memotong kalimat di tengah, selalu selesaikan kalimatnya.\n"
                "- Gunakan bahasa Indonesia informal/santai seperti chat biasa.\n"
                "- Jangan pakai markdown, bullet, atau simbol *, _, `, ~.\n"
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
                    max_output_tokens=150,
                    temperature=temperature,
                )
            )

            raw = response.text.strip() if response.text else None
            if not raw:
                print("[AIHandler] Gemini tidak menghasilkan teks")
                return None

            # Bersihkan lalu pastikan selalu selesai di tanda baca
            result = _trim_to_sentence(_clean(raw))
            print(f"[AIHandler] Balasan: {result[:100]}")
            return result if result else None

        except Exception as e:
            print(f"[AIHandler] ERROR: {e}")
            return None
