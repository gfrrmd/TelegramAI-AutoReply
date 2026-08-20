import google.generativeai as genai
from config import config
from database import Database


class AIHandler:
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(config.GEMINI_MODEL)
        self._db = Database()

    async def generate_reply(
        self,
        sender_id: int,
        sender_name: str,
        history: list,
        new_message: str
    ) -> str | None:
        try:
            # Cek apakah ada persona khusus untuk sender ini
            user_persona = await self._db.get_user_persona(sender_id)
            global_persona = await self._db.get_persona()

            if user_persona:
                # Pakai persona khusus untuk user ini
                system_prompt = (
                    f"{user_persona}\n\n"
                    f"Kamu sedang membalas pesan dari {sender_name}. "
                    f"Balas dengan natural, tidak terlihat seperti bot."
                )
            else:
                # Pakai persona global (default)
                system_prompt = (
                    f"{global_persona}\n\n"
                    f"Kamu sedang membalas pesan dari seseorang bernama {sender_name}. "
                    f"Balas dengan singkat, natural, dan tidak terlihat seperti bot. "
                    f"Jangan gunakan emoji berlebihan. Maksimal 3 kalimat."
                )

            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})
            contents.append({"role": "user", "parts": [new_message]})

            response = self.model.generate_content(
                contents,
                generation_config=genai.GenerationConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=200,
                    temperature=0.8 if user_persona else 0.7,
                )
            )

            return response.text.strip() if response.text else None

        except Exception as e:
            print(f"[AIHandler] Error: {e}")
            return None
