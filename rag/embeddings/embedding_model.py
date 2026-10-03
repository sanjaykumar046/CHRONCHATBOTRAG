import requests

from rag.config import (
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL
)


class EmbeddingModel:
    """
    Generates embeddings using the local Ollama server.
    """

    def generate_embedding(self, text: str) -> list:

        response = requests.post(
            f"{EMBEDDING_BASE_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=120
        )

        # Ollama's newer API uses /api/embed with an `input` field and
        # returns `embeddings`; keep the legacy endpoint for older installs.
        if response.status_code == 404:
            response = requests.post(
                f"{EMBEDDING_BASE_URL}/api/embed",
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text
                },
                timeout=120
            )

        response.raise_for_status()

        result = response.json()
        if "embedding" in result:
            return result["embedding"]
        embeddings = result.get("embeddings")
        if not embeddings:
            raise ValueError("Embedding response did not contain an embedding vector.")
        return embeddings[0]
