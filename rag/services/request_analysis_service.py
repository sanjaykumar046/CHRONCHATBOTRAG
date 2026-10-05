import json

from rag.config import REGISTRY_CANDIDATE_COUNT
from rag.llm.classifier_llm import ClassifierLLM
from rag.prompts.request_analysis_prompt import REQUEST_ANALYSIS_PROMPT
from rag.services.api_registry_service import APIRegistryService
from rag.services.intent_retriever import IntentRetriever


class RequestAnalysisService:
    """Combine query rewriting, routing, intent choice, and extraction."""

    CATEGORIES = {"small_talk", "off_talk", "on_talk"}
    ON_TALK_INTENTS = {"knowledge", "live_data"}

    def __init__(self):
        self.classifier = ClassifierLLM()
        self.registry_service = APIRegistryService()
        self.usable_registry = [
            entry for entry in self.registry_service.get_all()
            if entry.get("API Endpoint")
        ]
        self.retriever = IntentRetriever(self.usable_registry)

    @staticmethod
    def _history_text(history: list) -> str:
        turns = []
        for turn in history or []:
            user_text = str(turn.get("user", "")).strip()
            assistant_text = str(turn.get("assistant", "")).strip()
            if len(assistant_text) > 200:
                assistant_text = assistant_text[:200] + "..."
            turns.append({"user": user_text, "assistant": assistant_text})
        return json.dumps(turns, ensure_ascii=False)

    @staticmethod
    def _candidate_view(entry: dict) -> dict:
        return {
            "Intent Name": entry.get("Intent Name", ""),
            "Description": entry.get("Description", ""),
            "Example questions": entry.get("Example questions", ""),
            "Required Params": entry.get("Required Params", ""),
            "Optional Params": entry.get("Optional Params", ""),
        }

    def analyze(self, question: str, history: list = None) -> dict:
        prior_user_questions = [
            str(turn.get("user", "")).strip()
            for turn in (history or [])
            if str(turn.get("user", "")).strip()
        ]
        candidate_query = " ".join(prior_user_questions + [question])
        candidates = self.retriever.get_top_candidates(
            candidate_query,
            k=REGISTRY_CANDIDATE_COUNT,
        )
        candidate_views = [self._candidate_view(entry) for entry in candidates]
        candidate_names = {
            str(entry.get("Intent Name", "")).casefold(): entry
            for entry in candidates
        }

        prompt = REQUEST_ANALYSIS_PROMPT.format(
            history=self._history_text(history or []),
            question=question,
            candidates=json.dumps(candidate_views, ensure_ascii=False),
        )
        result = self.classifier.classify(
            prompt,
            fallback={},
        )
        if not isinstance(result, dict):
            return self._invalid_result("The request analyzer returned invalid JSON.")

        category = str(result.get("category", "")).strip().lower()
        if category not in self.CATEGORIES:
            return self._invalid_result("The request analyzer returned an unknown category.")

        normalized_question = result.get("normalized_question")
        if not isinstance(normalized_question, str) or not normalized_question.strip():
            normalized_question = question
        normalized_question = normalized_question.strip()

        analysis = {
            "status": "success",
            "category": category,
            "normalized_question": normalized_question,
            "source_question": question,
            "is_follow_up": bool(result.get("is_follow_up", False)),
            "parameter_evidence": candidate_query if result.get("is_follow_up") else question,
            "intent": None,
            "registry": None,
            "parameters": {},
            "confidence": result.get("confidence", 0.0),
            "reason": result.get("reason", ""),
            "response_mode": (
                "direct_metric"
                if result.get("response_mode") == "direct_metric"
                else "narrative"
            ),
        }

        if category != "on_talk":
            return analysis

        intent = str(result.get("intent", "")).strip().lower()
        if intent not in self.ON_TALK_INTENTS:
            return self._invalid_result("The request analyzer returned an unknown on-talk intent.")
        analysis["intent"] = intent

        if intent == "knowledge":
            return analysis

        selected_name = result.get("registry_intent")
        if not isinstance(selected_name, str) or selected_name.casefold() not in candidate_names:
            return {
                "status": "error",
                "message": "No matching live-data intent was selected from the registry candidates.",
                "details": {
                    "selected_intent": selected_name,
                    "candidate_intents": [entry.get("Intent Name") for entry in candidates],
                },
            }

        analysis["registry"] = candidate_names[selected_name.casefold()]
        parameters = result.get("parameters", {})
        analysis["parameters"] = parameters if isinstance(parameters, dict) else {}
        return analysis

    @staticmethod
    def _invalid_result(message: str) -> dict:
        return {"status": "error", "message": message}
