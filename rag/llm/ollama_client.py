import requests

from rag.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL
)


class OllamaClient:

    def generate(self, prompt: str, options: dict = None, json_mode: bool = False) -> str:

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": options or {}
        }

        if json_mode:
            payload["format"] = "json"

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=300
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]