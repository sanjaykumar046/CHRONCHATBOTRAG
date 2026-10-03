import json

from rag.llm.ollama_client import OllamaClient


class ClassifierLLM:

    def __init__(self):
        self.client = OllamaClient()

    def classify(self, prompt: str, fallback: dict) -> dict:
        """
        Send the prompt to the LLM and return the classification
        as a Python dictionary. `fallback` is returned on parse failure,
        so each stage can define its own safe default.
        """

        response = self.client.generate(
            prompt,
            options={
                "num_predict": 512,
                "temperature": 0
            },
            json_mode=True
        )

        response = response.strip()
        response = response.replace("```json", "")
        response = response.replace("```", "")
        response = response.replace("{{", "{")
        response = response.replace("}}", "}")
        response = response.strip()

        print("=" * 80)
        print("RAW LLM RESPONSE")
        print(response)
        print("=" * 80)

        try:
            return json.loads(response)

        except json.JSONDecodeError:
            print("JSON PARSE FAILED")
            return fallback
