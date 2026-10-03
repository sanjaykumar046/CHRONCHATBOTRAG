import chromadb

from rag.config import (
    CHROMA_DB_PATH,
    CHROMA_COLLECTION,
    TOP_K_RESULTS
)


class ChromaService:
    """
    Handles storing and retrieving vectors from ChromaDB.
    """

    def __init__(self):

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH)
        )

        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION
        )

    # =========================================================
    # Store Embeddings
    # =========================================================

    def store(self, embedded_chunks):

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in embedded_chunks:

            metadata = chunk["metadata"]

            ids.append(
                f"{metadata['source']}_{metadata['chunk_id']}"
            )

            documents.append(
                chunk["content"]
            )

            embeddings.append(
                chunk["embedding"]
            )

            metadatas.append(
                metadata
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        print(f"Stored {len(ids)} chunks.")

    # =========================================================
    # Search
    # =========================================================

    def search(self, query_embedding, top_k=TOP_K_RESULTS):

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        return results