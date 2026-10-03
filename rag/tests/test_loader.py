from rag.loaders.document_loader import DocumentLoader

loader = DocumentLoader()

documents = loader.load_documents()

print(f"Documents Loaded : {len(documents)}")

for doc in documents:
    print("-" * 50)
    print("Module :", doc["module"])
    print("Page   :", doc["page"])
    print("Source :", doc["source"])
    print(doc["content"][:200])