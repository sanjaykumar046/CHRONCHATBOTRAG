import time

from rag.services.retrieval_service import RetrievalService
from rag.services.prompt_service import PromptService
from rag.llm.ollama_client import OllamaClient


class ChatService:

    def __init__(self):

        self.retriever = RetrievalService()
        self.prompt_builder = PromptService()
        self.llm = OllamaClient()

    def ask(self, question):

        t0 = time.time()

        print("Searching knowledge base...")

        chunks = self.retriever.retrieve(question)

        t1 = time.time()
        print(f"[TIMING] Retrieval took {t1 - t0:.2f}s")
        print(f"Retrieved {len(chunks)} chunks")

        prompt = self.prompt_builder.build(
            question,
            chunks
        )

        t2 = time.time()
        print(f"[TIMING] Prompt build took {t2 - t1:.2f}s")
        print(f"[TIMING] Prompt length: {len(prompt)} characters")

        print("Generating answer...")

        answer = self.llm.generate(
            prompt
        )

        t3 = time.time()
        print(f"[TIMING] LLM generation took {t3 - t2:.2f}s")

        print(f"[TIMING] TOTAL chat_service.ask() time: {t3 - t0:.2f}s")

        return {
            "question": question,
            "answer": answer
        }
