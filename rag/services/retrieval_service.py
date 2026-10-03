from rag.embeddings.embedding_model import EmbeddingModel
from rag.vectorstore.chroma_service import ChromaService


class RetrievalService:

    def __init__(self):
        self.embedding_model = EmbeddingModel()
        self.chroma = ChromaService()

    def retrieve(self, question):

        # Generate embedding for the user's question
        query_embedding = self.embedding_model.generate_embedding(question)

        # Search ChromaDB
        results = self.chroma.search(query_embedding)

        # Extract Chroma response
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        retrieved_chunks = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances
        ):

            retrieved_chunks.append({
                "module": metadata.get("module"),
                "page": metadata.get("page"),
                "source": metadata.get("source"),
                "chunk_id": metadata.get("chunk_id"),
                "content": document,
                "distance": distance
            })

        return retrieved_chunks