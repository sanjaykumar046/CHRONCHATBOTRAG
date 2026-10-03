from rag.loaders.document_loader import DocumentLoader
from rag.utils.cleaner import TextCleaner

loader = DocumentLoader()

documents = loader.load_documents()

for doc in documents:

    cleaned_text = TextCleaner.clean(doc["content"])

    print("=" * 80)
    print(doc["page"])
    print("=" * 80)
    print(cleaned_text[:500])