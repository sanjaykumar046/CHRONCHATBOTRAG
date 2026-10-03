"""
Prompt Service

Builds the final prompt that is sent to the LLM.
"""

from rag.config import (
    MAX_RESPONSE_WORDS,
    MAX_RESPONSE_CHARACTERS,
    MAX_RESPONSE_PARAGRAPHS,
    MAX_RESPONSE_BULLETS
)


class PromptService:

    @staticmethod
    def build(question, retrieved_chunks):

        context = ""

        # ---------------------------------------------------------
        # Build Context
        # ---------------------------------------------------------

        for index, chunk in enumerate(retrieved_chunks, start=1):

            context += (
                f"\n========== Document {index} ==========\n"
                f"Module : {chunk['module']}\n"
                f"Page   : {chunk['page']}\n\n"
                f"{chunk['content']}\n"
            )

        # ---------------------------------------------------------
        # Build Prompt
        # ---------------------------------------------------------

        prompt = f"""
You are CHRONAI AI Assistant.

Answer the user's question ONLY using the provided context.

Response Rules:

1. Answer ONLY from the provided context.
2. Do NOT invent, assume, or generate information that is not present in the context.
3. If the answer is not found, reply exactly:
   "I couldn't find this information in the knowledge base."
4. Keep the response clear, concise, and professional.
5. Maximum {MAX_RESPONSE_WORDS} words.
6. Maximum {MAX_RESPONSE_CHARACTERS} characters.
7. Use no more than {MAX_RESPONSE_PARAGRAPHS} short paragraphs.
8. If explaining a process, use numbered steps.
9. If listing features or items, use a maximum of {MAX_RESPONSE_BULLETS} bullet points.
10. Do not repeat the same information.
11. Use simple and easy-to-understand English.
12. Highlight important page names, module names, and headings using Markdown bold (**Heading**).
13. Keep the answer suitable for a chat application.
14. End the response naturally without unnecessary explanations.
15. Do not mention the context, documents, retrieved chunks, or knowledge base unless the user specifically asks.
16. If the answer is longer than the configured limit, summarize it while preserving the key information.
17. Do not include introductory phrases like "Based on the provided context..." or "According to the knowledge base...".
18. Keep the response conversational and natural.

==================== CONTEXT ====================

{context}

=================================================

User Question:

{question}

Answer:
"""

        return prompt.strip()