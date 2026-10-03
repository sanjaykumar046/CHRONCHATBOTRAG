from rag.llm.classifier_llm import ClassifierLLM
from rag.prompts.query_rewriter_prompt import QUERY_REWRITER_PROMPT


class QueryRewriter:
    """
    Stage 0 - Conversational Query Rewriter

    Examines recent conversation history and rewrites follow-up
    questions (which use pronouns or omit entities) into self-contained
    standalone questions.

    If the question is already independent, it returns the original
    question unchanged.
    """

    def __init__(self):
        self.classifier = ClassifierLLM()

    def _format_history(self, history: list) -> str:
        formatted = []
        for i, turn in enumerate(history, 1):
            user_msg = turn.get("user", "").strip()
            asst_msg = turn.get("assistant", "").strip()
            # Truncate assistant message if too long to save token context
            if len(asst_msg) > 200:
                asst_msg = asst_msg[:200] + "..."
            formatted.append(f"Turn {i}:\nUser: {user_msg}\nAssistant: {asst_msg}")
        return "\n\n".join(formatted)

    def rewrite(self, question: str, history: list) -> dict:
        if not history or not isinstance(history, list):
            return {
                "is_follow_up": False,
                "rewritten_question": question,
                "reason": "No conversation history."
            }

        history_text = self._format_history(history)

        prompt = QUERY_REWRITER_PROMPT.format(
            history=history_text,
            question=question
        )

        result = self.classifier.classify(
            prompt,
            fallback={
                "is_follow_up": False,
                "rewritten_question": question,
                "reason": "Fallback: returned original question."
            }
        )

        if not isinstance(result, dict):
            return {
                "is_follow_up": False,
                "rewritten_question": question,
                "reason": "Classifier returned invalid format."
            }

        rewritten = result.get("rewritten_question", "").strip()
        if not rewritten:
            rewritten = question

        return {
            "is_follow_up": bool(result.get("is_follow_up", False)),
            "rewritten_question": rewritten,
            "reason": result.get("reason", "")
        }

