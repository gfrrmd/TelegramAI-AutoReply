import google.generativeai as genai
from config import config

genai.configure(api_key=config.GEMINI_API_KEY)


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

            if user_persona:
                system_prompt = (
                    f"{user_persona}\n\n"
                    f"Kamu sedang membalas pesan dari {sender_name}. "
                    f"Balas dengan natural, tidak terlihat seperti bot."
                )
                temperature = 0.8
                print(f"[AIHandler] Pakai persona khusus untuk {sender_name}")
            else:
                system_prompt = (
                    f"{global_persona}\n\n"
                    f"Kamu sedang membalas pesan dari seseorang bernama {sender_name}. "
                    f"Balas dengan singkat, natural, dan tidak terlihat seperti bot. "
                    f"Jangan gunakan emoji berlebihan. Maksimal 3 kalimat."
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

            result = response.text.strip() if response.text else None
            if result:
                print(f"[AIHandler] Balasan berhasil dibuat: {result[:80]}")
            else:
                print(f"[AIHandler] Gemini tidak menghasilkan teks (response kosong)")
            return result

        except Exception as e:
            print(f"[AIHandler] ERROR: {e}")
            return None
