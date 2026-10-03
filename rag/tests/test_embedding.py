from rag.loaders.document_loader import DocumentLoader
from rag.utils.cleaner import TextCleaner
from rag.utils.chunker import TextChunker
from rag.services.embedding_service import EmbeddingService


loader = DocumentLoader()
documents = loader.load_documents()

document = documents[0]

document["content"] = TextCleaner.clean(document["content"])

chunks = TextChunker.chunk(document)

service = EmbeddingService()

embedded_chunks = service.generate(chunks)

print("=" * 80)

print("Module :", embedded_chunks[0]["module"])
print("Page   :", embedded_chunks[0]["page"])
print("Chunk  :", embedded_chunks[0]["chunk_id"])

print()

print("Embedding Length :", len(embedded_chunks[0]["embedding"]))

print()

print("First 10 Values")

print(embedded_chunks[0]["embedding"][:10])