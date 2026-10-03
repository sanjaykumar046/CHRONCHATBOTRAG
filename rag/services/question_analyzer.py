from rag.llm.classifier_llm import ClassifierLLM
from rag.prompts.live_data_intent_prompt import LIVE_DATA_INTENT_PROMPT
from rag.services.api_registry_service import APIRegistryService
from rag.services.intent_retriever import IntentRetriever


class QuestionAnalyzer:
    """
    Stage 3 - Live Data Question Analyzer

    Responsibilities
    ----------------
    1. Load API Registry
    2. Narrow candidates using cached embedding similarity (IntentRetriever)
    3. Ask the LLM to identify the user's intent from the narrowed list
    4. Validate the intent exists in the registry
    5. Return the matched registry entry

    Does NOT:
    - Perform RBAC
    - Resolve parameters
    - Call APIs
    """

    def __init__(self):
        self.classifier = ClassifierLLM()
        self.registry_service = APIRegistryService()

        # Only intents with a real backend can ever produce a working
        # answer - excluding the rest from retrieval means a dead-end
        # intent (no "API Endpoint") can never out-compete a working
        # one just because its phrasing happens to overlap. The LLM
        # has no way to know an intent is unwired from the slim
        # candidate view alone, so it must never see one as an option.
        usable_registry = [
            entry for entry in self.registry_service.get_all()
            if entry.get("API Endpoint")
        ]
        self.retriever = IntentRetriever(usable_registry)

    def _build_slim_candidates(self, candidates: list) -> list:
        return [
            {
                "Intent Name": entry["Intent Name"],
                # Trim description to keep prompt size down — the LLM
                # only needs enough to distinguish between candidates
                "Description": entry.get("Description", "")[:120],
                "Required Params": entry.get("Required Params", "")
            }
            for entry in candidates
        ]

    def analyze(self, question: str, top_k: int = 5) -> dict:

        # ---------------------------------------------------------
        # Narrow Candidates (embedding retrieval)
        # ---------------------------------------------------------

        candidates = self.retriever.get_top_candidates(question, k=top_k)

        if not candidates:
            return {
                "status": "error",
                "message": "No matching live data intent found for this question.",
                "details": {
                    "reason": "No registry entries met the similarity threshold."
                }
            }

        slim_candidates = self._build_slim_candidates(candidates)

        # ---------------------------------------------------------
        # Build Prompt
        # ---------------------------------------------------------

        prompt = LIVE_DATA_INTENT_PROMPT.format(
            question=question,
            registry=slim_candidates
        )

        # ---------------------------------------------------------
        # LLM Classification
        # ---------------------------------------------------------

        result = self.classifier.classify(
            prompt,
            fallback={
                "intent": None,
                "confidence": 0.0,
                "reason": "Unable to identify live data intent."
            }
        )

        intent = result.get("intent")

        if not intent or intent == "NO_MATCH":
            return {
                "status": "error",
                "message": "No matching live data intent found for this question.",
                "details": result
            }

        # ---------------------------------------------------------
        # Registry Lookup (full entry, unchanged)
        # ---------------------------------------------------------

        registry_entry = self.registry_service.get_by_intent(intent)

        if registry_entry is None:
            return {
                "status": "error",
                "message": f"Intent '{intent}' not found in API Registry.",
                "details": {
                    "llm_returned_intent": intent,
                    "candidates_shown_to_llm": [c["Intent Name"] for c in slim_candidates]
                }
            }

        # ---------------------------------------------------------
        # Success
        # ---------------------------------------------------------

        return {
            "status": "success",
            "intent": intent,
            "confidence": result.get("confidence", 0.0),
            "reason": result.get("reason", ""),
            "registry": registry_entry
        }