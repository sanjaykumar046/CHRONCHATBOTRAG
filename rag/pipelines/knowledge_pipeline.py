"""
Knowledge Pipeline

Handles all knowledge-based requests by executing
the RAG pipeline.
"""

from rag.services.chat_service import ChatService


class KnowledgePipeline:

    def __init__(self):

        self.chat_service = ChatService()

    def execute(self, request: dict):

        question = request.get("message")

        if not question:
            return {
                "status": "error",
                "message": "Question is required."
            }

        result = self.chat_service.ask(question)

        return {
            "status": "success",
            "pipeline": "knowledge",
            "data": result
        }