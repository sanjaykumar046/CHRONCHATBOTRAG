from rag.services.retrieval_service import RetrievalService
from rag.services.prompt_service import PromptService

question = "How can an employee raise an issue?"

retriever = RetrievalService()

chunks = retriever.retrieve(question)

prompt = PromptService.build(
    question,
    chunks
)

print(prompt)