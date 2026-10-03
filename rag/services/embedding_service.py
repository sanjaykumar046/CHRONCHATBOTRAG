from rag.embeddings.embedding_model import EmbeddingModel


class EmbeddingService:
    """
    Generates embeddings for text chunks.
    """

    def __init__(self):
        self.embedding_model = EmbeddingModel()

    def generate(self, chunks):
        """
        Generate embeddings for each chunk.

        Input:
        [
            {
                "content": "...",
                "metadata": {...}
            }
        ]

        Output:
        [
            {
                "content": "...",
                "metadata": {...},
                "embedding": [...]
            }
        ]
        """

        embedded_chunks = []

        for chunk in chunks:

            embedding = self.embedding_model.generate_embedding(
                chunk["content"]
            )

            embedded_chunks.append({
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "embedding": embedding
            })

        return embedded_chunks