from rag.vectorstore.chroma_service import ChromaService

chroma = ChromaService()

results = chroma.collection.get()

print(f"Total Records: {len(results['ids'])}")

print("=" * 100)

for i in range(len(results["ids"])):

    print(f"ID        : {results['ids'][i]}")
    print(f"Metadata  : {results['metadatas'][i]}")
    print(f"Document  : {results['documents'][i][:300]}...")
    print("-" * 100)