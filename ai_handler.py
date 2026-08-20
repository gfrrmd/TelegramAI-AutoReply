import google.generativeai as genai
from config import config
from database import Database

db_ref = None  # akan di-set dari main


class AIHandler:
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(config.GEMINI_MODEL)
        self._db = Database()

    async def generate_reply(self, sender_name: str, history: list, new_message: str) -> str | None:
        try:
            persona = await self._db.get_persona()

            system_prompt = (
                f"{persona}\n\n"
                f"Kamu sedang membalas pesan dari seseorang bernama {sender_name}. "
                f"Balas dengan singkat, natural, dan tidak terlihat seperti bot. "
                f"Jangan gunakan emoji berlebihan. Maksimal 3 kalimat."
            )

            # Bangun riwayat percakapan untuk konteks
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})

            # Tambahkan pesan baru
            contents.append({"role": "user", "parts": [new_message]})

            response = self.model.generate_content(
                contents,
                generation_config=genai.GenerationConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=200,
                    temperature=0.7,
                )
            )

            return response.text.strip() if response.text else None

        except Exception as e:
            print(f"[AIHandler] Error: {e}")
            return None
