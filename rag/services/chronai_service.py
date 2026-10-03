import time

from rag.prompts.category_prompt import CATEGORY_PROMPT
from rag.prompts.intent_prompt import INTENT_PROMPT
from rag.llm.classifier_llm import ClassifierLLM
from rag.router.request_router import RequestRouter


class ChronAIService:

    def __init__(self):
        self.classifier = ClassifierLLM()
        self.router = RequestRouter()

    def handle(self, question: str, user=None, session=None) -> dict:

        t0 = time.time()

        # ---------------------------------------------------------
        # Stage 1: category classification
        # ---------------------------------------------------------

        category_prompt = CATEGORY_PROMPT.format(question=question)

        category_result = self.classifier.classify(
            category_prompt,
            fallback={
                "category": "off_talk",
                "normalized_question": question,
                "confidence": 0.0,
                "reason": "Unable to parse category classification."
            }
        )

        t1 = time.time()
        print(f"[TIMING] Stage 1 (category) took {t1 - t0:.2f}s")
        print(f"[CATEGORY] category={category_result.get('category')} "
              f"confidence={category_result.get('confidence')}")

        category = category_result.get("category")
        normalized_question = category_result.get("normalized_question") or question

        classification = {
            "category": category,
            "intent": None,
            "normalized_question": normalized_question,
            "category_confidence": category_result.get("confidence"),
            "category_reason": category_result.get("reason")
        }

        # ---------------------------------------------------------
        # Stage 2: intent classification (only for on_talk)
        # ---------------------------------------------------------

        if category == "on_talk":

            intent_prompt = INTENT_PROMPT.format(question=normalized_question)

            intent_result = self.classifier.classify(
                intent_prompt,
                fallback={
                    "intent": "knowledge",
                    "confidence": 0.0,
                    "reason": "Unable to parse intent classification."
                }
            )

            t2 = time.time()
            print(f"[TIMING] Stage 2 (intent) took {t2 - t1:.2f}s")
            print(f"[INTENT] intent={intent_result.get('intent')} "
                  f"confidence={intent_result.get('confidence')}")

            classification["intent"] = intent_result.get("intent")
            classification["intent_confidence"] = intent_result.get("confidence")
            classification["intent_reason"] = intent_result.get("reason")

        # ---------------------------------------------------------
        # Route to the correct pipeline
        # ---------------------------------------------------------

        request = {
            "question": question,
            "normalized_question": normalized_question,
            "session_id": session   # add this

        }

        result = self.router.route(classification, request, user=user, session=session)

        t3 = time.time()
        print(f"[TIMING] Routing + pipeline execution took {t3 - t1:.2f}s")
        print(f"[TIMING] TOTAL chronai_service.handle() time: {t3 - t0:.2f}s")

        result["classification"] = classification

        return result