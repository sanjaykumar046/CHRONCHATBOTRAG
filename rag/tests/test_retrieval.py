from rag.services.retrieval_service import RetrievalService

retriever = RetrievalService()

question = "How can an employee raise an issue?"

results = retriever.retrieve(question)

print("=" * 80)

for index, result in enumerate(results, start=1):

    print(f"\nResult {index}")
    print("-" * 80)

    print(f"Module    : {result['module']}")
    print(f"Page      : {result['page']}")
    print(f"Source    : {result['source']}")
    print(f"Chunk ID  : {result['chunk_id']}")
    print(f"Distance  : {result['distance']}")

    print()

    print(result["content"][:500])