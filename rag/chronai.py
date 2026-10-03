"""
ChronAI Engine

Main entry point for all AI requests.

Flow:

User Request
      │
      ▼
Pending ASK_USER session? ──► yes ──► Live Data Pipeline (merge reply) ──► Final Response
      │
      no
      ▼
Category Classifier (small_talk / off_talk / on_talk)
      │
      ├── (small_talk / off_talk) ──► direct response
      │
      └── on_talk
              │
              ▼
        Intent Classifier (knowledge / live_data)
              │
              ▼
        Request Router
              │
              ▼
        Knowledge / Live Data Pipeline
              │
              ▼
        Final Response
"""

from rag.prompts.category_prompt import CATEGORY_PROMPT
from rag.prompts.intent_prompt import INTENT_PROMPT
from rag.llm.classifier_llm import ClassifierLLM
from rag.router.request_router import RequestRouter
from rag.services.query_rewriter import QueryRewriter
from rag.services.session_store import SessionStore
import re


class ChronAI:

    def __init__(self):

        self.classifier = ClassifierLLM()
        self.request_router = RequestRouter()
        self.query_rewriter = QueryRewriter()
        self.session_store = SessionStore()

    def process(self, request: dict):

        # -------------------------------------------------
        # Validate Request
        # -------------------------------------------------

        question = request.get("message", "").strip()

        if not question:
            return {
                "status": "error",
                "message": "Question is required."
            }

        # -------------------------------------------------
        # Extract user context and session id up front, since both
        # the pending-session check below and the normal routing
        # path further down need them.
        # -------------------------------------------------

        user = {
            "userid": request.get("userid"),
            "access_role": request.get("access_role")
        } if request.get("userid") or request.get("access_role") else None

        session = request.get("session_id")
        current_userid = user.get("userid") if user else None

        # -------------------------------------------------
        # Check for a pending ASK_USER session FIRST, before running
        # any classification.
        #
        # If the previous turn asked the user for a missing parameter
        # (e.g. "please provide dateRange"), this message is the
        # answer to that question, not a new question. A bare reply
        # like a date range or an employee ID will often not resemble
        # an app question on its own, so running it through the
        # category/intent classifier would misclassify it. Instead,
        # go straight to whichever pipeline owns the pending session
        # so it can merge the reply into the parameters it already
        # has and continue from where it left off.
        # -------------------------------------------------

        if self.request_router.has_pending_session(session, userid=current_userid):

            response = self.request_router.route_pending_reply(
                request=request,
                user=user,
                session=session
            )

            # Record turn in conversation history if final response was produced
            if isinstance(response, dict) and response.get("status") == "success":
                reply_text = response.get("reply") or response.get("message") or "Completed."
                self.session_store.save_turn(session, question, reply_text, userid=current_userid)

            return {
                "status": "success",
                "original_question": question,
                "normalized_question": question,
                "classification": None,
                "response": response
            }

        # -------------------------------------------------
        # Stage 0: Conversational Query Rewriting
        # (Resolves follow-ups, pronouns, and implicit context from history)
        # -------------------------------------------------

        history = self.session_store.get_history(session, userid=current_userid)
        if history:
            rewrite_result = self.query_rewriter.rewrite(question, history)
            if rewrite_result.get("is_follow_up") and rewrite_result.get("rewritten_question"):
                active_question = rewrite_result["rewritten_question"]
                print(f"[QueryRewriter] Rewrote follow-up '{question}' -> '{active_question}'")
            else:
                active_question = question
        else:
            active_question = question

        # -------------------------------------------------
        # Stage 1: Category Classification
        # -------------------------------------------------

        category_prompt = CATEGORY_PROMPT.format(question=active_question)

        category_result = self.classifier.classify(
            category_prompt,
            fallback={
                "category": "off_talk",
                "normalized_question": active_question,
                "confidence": 0.0,
                "reason": "Unable to parse category classification."
            }
        )

        category = category_result.get("category")
        normalized_question = category_result.get("normalized_question") or active_question

        # Small local models sometimes copy the illustrative response from
        # the prompt and replace the user's question with an unrelated one.
        # Keep clear reportee list requests deterministic: this is live org
        # data and must reach the registry-backed pipeline.
        reportee_request = bool(re.search(
            r"\b(reportees?|direct reports?|team members|who reports to me)\b",
            active_question,
            re.IGNORECASE
        )) and bool(re.search(
            r"\b(show|list|get|fetch|display|who|which|give me|my)\b",
            active_question,
            re.IGNORECASE
        )) and not bool(re.search(r"\b(how do i|how can i|where can i)\b", active_question, re.IGNORECASE))

        if reportee_request:
            category = "on_talk"
            normalized_question = active_question

        classification = {
            "category": category,
            "intent": None,
            "normalized_question": normalized_question,
            "category_confidence": category_result.get("confidence"),
            "category_reason": category_result.get("reason")
        }

        # -------------------------------------------------
        # Stage 2: Intent Classification (on_talk only)
        # -------------------------------------------------

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

            classification["intent"] = intent_result.get("intent")
            classification["intent_confidence"] = intent_result.get("confidence")
            classification["intent_reason"] = intent_result.get("reason")

            if reportee_request:
                classification["intent"] = "live_data"
                classification["intent_confidence"] = 1.0
                classification["intent_reason"] = "Request for the user's reportee list requires live organizational data."

        # -------------------------------------------------
        # Update the request so all downstream pipelines
        # use the corrected question.
        # -------------------------------------------------

        request["message"] = normalized_question

        # -------------------------------------------------
        # Route Request
        # -------------------------------------------------

        response = self.request_router.route(
            classification=classification,
            request=request,
            user=user,
            session=session
        )

        # -------------------------------------------------
        # Save Conversation Turn in History
        # -------------------------------------------------

        if isinstance(response, dict) and response.get("status") == "success":
            reply_text = (
                response.get("reply")
                or response.get("message")
                or (response.get("data", {}) if isinstance(response.get("data"), dict) else {}).get("answer")
                or "Here are the results."
            )
            self.session_store.save_turn(
                session_id=session,
                user_message=question,
                bot_reply=reply_text,
                userid=current_userid
            )

        # -------------------------------------------------
        # Final Response
        # -------------------------------------------------

        return {
            "status": "success",
            "original_question": question,
            "normalized_question": normalized_question,
            "classification": classification,
            "response": response
        }
