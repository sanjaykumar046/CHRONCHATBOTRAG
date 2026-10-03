from rag.prompts.intent_prompt import INTENT_PROMPT
from rag.llm.intent_llm import IntentLLM


class IntentClassifier:

    def __init__(self):
        self.llm = IntentLLM()

    def classify(self, question: str):

        prompt = INTENT_PROMPT.replace(
            "{question}",
            question
        )

        result = self.llm.classify(prompt)

        return result