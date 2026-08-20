import google.generativeai as genai
from config import config

genai.configure(api_key=config.GEMINI_API_KEY)


class AIHandler:
    def __init__(self, db):
        # Terima db instance dari main agar pakai pool yang sudah di-init
        self._db = db

    async def generate_reply(
        self,
        sender_id: int,
        sender_name: str,
        history: list,
        new_message: str
    ) -> str | None:
        try:
            user_persona = await self._db.get_user_persona(sender_id)
            global_persona = await self._db.get_persona()

            if user_persona:
                system_prompt = (
                    f"{user_persona}\n\n"
                    f"Kamu sedang membalas pesan dari {sender_name}. "
                    f"Balas dengan natural, tidak terlihat seperti bot."
                )
                temperature = 0.8
            else:
                system_prompt = (
                    f"{global_persona}\n\n"
                    f"Kamu sedang membalas pesan dari seseorang bernama {sender_name}. "
                    f"Balas dengan singkat, natural, dan tidak terlihat seperti bot. "
                    f"Jangan gunakan emoji berlebihan. Maksimal 3 kalimat."
                )
                temperature = 0.7

            # system_instruction harus dipass ke GenerativeModel, bukan GenerationConfig
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

            return response.text.strip() if response.text else None

        except Exception as e:
            print(f"[AIHandler] Error: {e}")
            return None
