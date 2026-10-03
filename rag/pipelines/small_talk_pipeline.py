from datetime import datetime

from rag.llm.ollama_client import OllamaClient
from rag.prompts.small_talk_prompt import SMALL_TALK_PROMPT


class SmallTalkPipeline:

    def __init__(self):
        self.client = OllamaClient()

    def execute(self, request: dict, normalized_question: str) -> dict:

        current_datetime = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

        prompt = SMALL_TALK_PROMPT.format(
            question=normalized_question,
            current_datetime=current_datetime
        )

        try:
            reply = self.client.generate(
                prompt,
                options={
                    "num_predict": 80,
                    "temperature": 0.6
                },
                json_mode=False
            )

            reply = reply.strip()

            if not reply:
                reply = "Hi! How can I help you today?"

        except Exception as e:
            print("SMALL TALK PIPELINE ERROR:", e)
            reply = "Hi! How can I help you today?"

        return {
            "status": "success",
            "pipeline": "small_talk",
            "message": reply
        }
