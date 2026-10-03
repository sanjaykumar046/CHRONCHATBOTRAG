from rag.loaders.document_loader import DocumentLoader
from rag.utils.cleaner import TextCleaner
from rag.utils.chunker import TextChunker


loader = DocumentLoader()

documents = loader.load_documents()

print(f"Documents : {len(documents)}")

for document in documents:

    cleaned_text = TextCleaner.clean(document["content"])

    document["content"] = cleaned_text

    chunks = TextChunker.chunk(document)

    print("=" * 80)
    print(document["page"])
    print(f"Chunks : {len(chunks)}")

    for chunk in chunks:

        print("-" * 50)
        print(f"Chunk {chunk['chunk_id']}")
        print(chunk["content"][:200])