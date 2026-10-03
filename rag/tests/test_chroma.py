from rag.loaders.document_loader import DocumentLoader
from rag.utils.cleaner import TextCleaner
from rag.utils.chunker import TextChunker
from rag.services.embedding_service import EmbeddingService
from rag.vectorstore.chroma_service import ChromaService

loader = DocumentLoader()

documents = loader.load_documents()

document = documents[0]

document["content"] = TextCleaner.clean(
    document["content"]
)

chunks = TextChunker.chunk(document)

embedding_service = EmbeddingService()

embedded_chunks = embedding_service.generate(
    chunks
)

chroma = ChromaService()

chroma.store(
    embedded_chunks
)