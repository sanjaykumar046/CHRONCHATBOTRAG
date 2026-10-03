from rag.loaders.document_loader import DocumentLoader
from rag.utils.cleaner import TextCleaner
from rag.utils.chunker import TextChunker
from rag.preprocess.metadata import MetadataGenerator
from rag.services.embedding_service import EmbeddingService
from rag.vectorstore.chroma_service import ChromaService


class IngestService:

    def __init__(self):

        self.loader = DocumentLoader()
        self.embedding_service = EmbeddingService()
        self.chroma_service = ChromaService()

    def run(self):

        print("=" * 80)
        print("Starting Knowledge Base Ingestion")
        print("=" * 80)

        documents = self.loader.load_documents()

        print(f"Documents Found : {len(documents)}")
        print()

        total_chunks = 0

        for index, document in enumerate(documents, start=1):

            print(f"[{index}/{len(documents)}] {document['page']}")

            # -------------------------------------------------
            # Step 1 : Clean Document
            # -------------------------------------------------
            document["content"] = TextCleaner.clean(
                document["content"]
            )

            # -------------------------------------------------
            # Step 2 : Split into Chunks
            # -------------------------------------------------
            chunks = TextChunker.chunk(document)

            # -------------------------------------------------
            # Step 3 : Generate Metadata
            # -------------------------------------------------
            for chunk_index, chunk in enumerate(chunks):

                chunk["metadata"] = MetadataGenerator.generate(
                    document=document,
                    chunk_id=chunk_index
                )

            total_chunks += len(chunks)

            # -------------------------------------------------
            # Step 4 : Generate Embeddings
            # -------------------------------------------------
            embedded_chunks = self.embedding_service.generate(
                chunks
            )

            # -------------------------------------------------
            # Step 5 : Store in ChromaDB
            # -------------------------------------------------
            self.chroma_service.store(
                embedded_chunks
            )

            print(f"   Stored {len(embedded_chunks)} chunks")

        print()
        print("=" * 80)
        print("Ingestion Completed")
        print("=" * 80)
        print(f"Documents : {len(documents)}")
        print(f"Chunks    : {total_chunks}")