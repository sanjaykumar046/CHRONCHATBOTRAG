from rag.vectorstore.chroma_service import ChromaService

chroma = ChromaService()

results = chroma.collection.get()

print("Total Chunks:", len(results["ids"]))
print()

print("Metadata of First Chunk")
print("-" * 50)
print(results["metadatas"][0])